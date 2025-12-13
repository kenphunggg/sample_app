#!/bin/bash

# --- ANSI Color Codes ---
GREEN='\033[0;32m' # For success messages
YELLOW='\033[0;33m' # For warnings/waiting
RED='\033[0;31m'   # For errors
BLUE='\033[0;34m'  # For informational steps
MAGENTA='\033[0;35m' # For response bodies
NC='\033[0m'       # No Color (to reset the format)

# --- Argument Check and Configuration ---
RAW_CPU_INPUT="$1"
DEFAULT_CPU_LIMIT="400"
if [ -z "$RAW_CPU_INPUT" ]; then
    RAW_CPU_INPUT="$DEFAULT_CPU_LIMIT"
    echo -e "${YELLOW}No CPU limit provided. Defaulting to ${RAW_CPU_INPUT}mCPU.${NC}" >&2
elif ! [[ "$RAW_CPU_INPUT" =~ ^[0-9]+$ ]]; then
    echo -e "${YELLOW}Invalid input ('$RAW_CPU_INPUT'). Must be a number. Defaulting to ${DEFAULT_CPU_LIMIT}mCPU.${NC}" >&2
    RAW_CPU_INPUT="$DEFAULT_CPU_LIMIT"
else
    echo -e "${BLUE}Using provided CPU limit: ${RAW_CPU_INPUT}mCPU.${NC}" >&2
fi

NAMESPACE="serverless"
SERVICE_NAME="measure-yolo"
NEW_CPU_LIMIT="${RAW_CPU_INPUT}m"
SERVICE_URL="http://${SERVICE_NAME}.${NAMESPACE}/detect" 
IMAGE_PATH="analyze_image/4k.jpg"
CONTAINER_TO_PATCH="user-container" 
CURL_FORMAT="%{http_code}|%{time_total}" 
TEMP_BODY_FILE="./.curl_temp_body.txt"

# --- Helper Function for Curl and Output ---
perform_curl_test() {
    local request_type="$1"
    
    touch "$TEMP_BODY_FILE"
    FORMATTED_OUTPUT=$(curl -s -X POST -F "image=@${IMAGE_PATH}" "$SERVICE_URL" -w "$CURL_FORMAT" -o "$TEMP_BODY_FILE")
    
    HTTP_CODE=$(echo "$FORMATTED_OUTPUT" | cut -d'|' -f1)
    LATENCY=$(echo "$FORMATTED_OUTPUT" | cut -d'|' -f2)
    RESPONSE_BODY=$(cat "$TEMP_BODY_FILE")
    
    echo -e "  Request Type: ${request_type}" >&2
    echo -e "  HTTP Status: ${GREEN}${HTTP_CODE}${NC}" >&2
    echo -e "  Latency: ${GREEN}${LATENCY} seconds${NC}" >&2
    echo -e "  Response Body:${MAGENTA}" >&2
    echo "$RESPONSE_BODY" | head -n 10 >&2
    echo -e "${NC}" >&2
    
    rm -f "$TEMP_BODY_FILE" >&2
    
    echo "$LATENCY" 
    return "$HTTP_CODE" 
}
# --- End of Helper Function ---


echo -e "${BLUE}--- 1. Applying Knative Service (knative.yaml) ---${NC}"
kubectl apply -f deploy/knative.yaml
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to apply Knative manifests.${NC}"
    exit 1
fi

echo -e "${YELLOW}Waiting 5 seconds for Knative resources to stabilize...${NC}"
sleep 5s 

echo -e "${YELLOW}--- Waiting for Knative Service ${SERVICE_NAME} to become Ready ---${NC}"
kubectl wait --namespace "$NAMESPACE" ksvc/"$SERVICE_NAME" --for=condition=Ready --timeout=300s
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Knative Service failed to become ready.${NC}"
    exit 1
fi

# --- NEW STEP: Robust Pod Readiness Check ---
echo -e "${YELLOW}--- Ensuring Pod is Found and Ready for Routing ---${NC}"

# Loop to find the Pod name
MAX_RETRIES=10
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    
    # *** SIMPLIFIED POD NAME RETRIEVAL ***
    POD_NAME=$(kubectl -n "$NAMESPACE" get pods --field-selector=status.phase=Running -o jsonpath='{.items[0].metadata.name}' 2>/dev/null)
    # ------------------------------------
    
    if [ -n "$POD_NAME" ]; then
        # Wait for the specific Pod to be ready (needed for stable patching)
        kubectl wait --namespace "$NAMESPACE" pod/"$POD_NAME" --for=condition=Ready --timeout=60s
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Found and confirmed Pod ready: ${POD_NAME}${NC}" >&2
            break
        fi
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo -e "${YELLOW}Attempt ${RETRY_COUNT}/${MAX_RETRIES}: Pod not yet stable. Waiting 3s...${NC}" >&2
    sleep 3
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo -e "${RED}ERROR: Failed to find a stable running Pod after multiple retries. Exiting.${NC}"
    exit 1
fi
# --- END NEW STEP ---


# --- 2. Initial Model Load Test (Warm-up) ---
echo -e "${BLUE}--- 2. Initial Warm-up Request (Logs redirected to /dev/null) ---${NC}"
# We must run this test to prime the container and ensure the model loads before baseline timing
perform_curl_test "Warm-up" > /dev/null
WARMUP_CODE=$?

if [ "$WARMUP_CODE" -ne 200 ]; then
    echo -e "${RED}ERROR: Warm-up request failed. HTTP Status Code: $WARMUP_CODE${NC}"
    exit 1
fi
echo -e "${GREEN}Warm-up successful.${NC}"


# --- 3. First Performance Test (Baseline) ---
echo -e "${BLUE}--- 3. Baseline Performance Test (High Resource) ---${NC}"
BASELINE_LATENCY=$(perform_curl_test "Baseline") 

# --- 4. Identifying Pod and Patch CPU Resources ---
echo -e "${BLUE}--- 4. Identifying Pod and Applying In-Place CPU Downscaling ---${NC}"

echo -e "Applying CPU change to ${YELLOW}${NEW_CPU_LIMIT}${NC} on container ${CONTAINER_TO_PATCH} in Pod: ${POD_NAME}..."

# Patching only limits for the user-container
PATCH_CMD='{"spec":{"containers":[{"name":"'"${CONTAINER_TO_PATCH}"'", "resources":{"limits":{"cpu":"'"${NEW_CPU_LIMIT}"'"}}}]}}'

kubectl -n "$NAMESPACE" patch pod "$POD_NAME" --subresource resize --patch "$PATCH_CMD"

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}WARNING: Patch command failed. CPU resources were likely NOT changed (In-Place Resize not supported or QOS issue).${NC}" 
fi 

# --- 5. Post-Patch Performance Tests (Multiple Runs) ---

echo -e "${BLUE}--- 5a. Post-Patch Performance Test 1 (New Limit: ${NEW_CPU_LIMIT}) ---${NC}"
PATCHED_LATENCY_1=$(perform_curl_test "Post-Patch 1")

sleep 1

echo -e "${BLUE}--- 5b. Post-Patch Performance Test 2 (New Limit: ${NEW_CPU_LIMIT}) ---${NC}"
PATCHED_LATENCY_2=$(perform_curl_test "Post-Patch 2")

sleep 1

echo -e "${BLUE}--- 5c. Post-Patch Performance Test 3 (New Limit: ${NEW_CPU_LIMIT}) ---${NC}"
PATCHED_LATENCY_3=$(perform_curl_test "Post-Patch 3")


echo -e "${GREEN}--- Final Comparison ---${NC}"
echo -e "Baseline Latency (High CPU): ${GREEN}${BASELINE_LATENCY} seconds${NC}"
echo -e "Patched Latency (Run 1 / ${NEW_CPU_LIMIT}): ${RED}${PATCHED_LATENCY_1} seconds${NC}"
echo -e "Patched Latency (Run 2 / ${NEW_CPU_LIMIT}): ${RED}${PATCHED_LATENCY_2} seconds${NC}"
echo -e "Patched Latency (Run 3 / ${NEW_CPU_LIMIT}): ${RED}${PATCHED_LATENCY_3} seconds${NC}"

kubectl delete -f deploy/knative.yaml

echo -e "${GREEN}--- Script Finished ---${NC}"