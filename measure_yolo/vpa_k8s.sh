#!/bin/bash

# --- ANSI Color Codes ---
GREEN='\033[0;32m' # For success messages
YELLOW='\033[0;33m' # For warnings/waiting
RED='\033[0;31m'   # For errors
BLUE='\033[0;34m'  # For informational steps
MAGENTA='\033[0;35m' # For response bodies
NC='\033[0m'       # No Color (to reset the format)

# --- Argument Check and Configuration ---

# 1. Read the raw input
RAW_CPU_INPUT="$1"
DEFAULT_CPU_LIMIT="400"

# 2. Input Validation and Defaulting Logic
if [ -z "$RAW_CPU_INPUT" ]; then
    # Case 1: No input provided (Empty string)
    RAW_CPU_INPUT="$DEFAULT_CPU_LIMIT"
    echo -e "${YELLOW}No CPU limit provided. Defaulting to ${RAW_CPU_INPUT}mCPU.${NC}" >&2
elif ! [[ "$RAW_CPU_INPUT" =~ ^[0-9]+$ ]]; then
    # Case 2: Wrong input (Non-numeric, e.g., 'adjshjd')
    echo -e "${YELLOW}Invalid input ('$RAW_CPU_INPUT'). Must be a number. Defaulting to ${DEFAULT_CPU_LIMIT}mCPU.${NC}" >&2
    RAW_CPU_INPUT="$DEFAULT_CPU_LIMIT"
else
    # Case 3: Valid numeric input provided
    echo -e "${BLUE}Using provided CPU limit: ${RAW_CPU_INPUT}mCPU.${NC}" >&2
fi

# 3. Construct the final CPU limit string
NAMESPACE="serverless"
DEPLOYMENT_NAME="measure-yolo"
SERVICE_URL="http://${DEPLOYMENT_NAME}.${NAMESPACE}/detect" 
IMAGE_PATH="analyze_image/4k.jpg"
NEW_CPU_LIMIT="${RAW_CPU_INPUT}m"
# -----------------------------------------------------------
CURL_FORMAT="%{http_code}|%{time_total}" 
# *** CHANGED: Use a hidden file in the current directory ***
TEMP_BODY_FILE="./.curl_temp_body.txt"
# -----------------------------------------------------------

# --- Helper Function for Curl and Output ---
# This function sends the request, writes the body to a temp file, and captures status/latency.
perform_curl_test() {
    local request_type="$1"
    
    # *** ADDED: Create the file defensively before curl runs. ***
    touch "$TEMP_BODY_FILE"
    
    # Capture the formatted output (status code and latency) to a variable,
    # writing the actual response body to a temporary file.
    FORMATTED_OUTPUT=$(curl -s -X POST -F "image=@${IMAGE_PATH}" "$SERVICE_URL" -w "$CURL_FORMAT" -o "$TEMP_BODY_FILE")
    
    # Extract Status Code and Latency from the clean formatted output
    HTTP_CODE=$(echo "$FORMATTED_OUTPUT" | cut -d'|' -f1)
    LATENCY=$(echo "$FORMATTED_OUTPUT" | cut -d'|' -f2)
    
    # Read the Response Body from the temp file
    RESPONSE_BODY=$(cat "$TEMP_BODY_FILE")
    
    # *** REDIRECTING ALL LOG OUTPUT TO STANDARD ERROR (>&2) ***
    echo -e "  Request Type: ${request_type}" >&2
    echo -e "  HTTP Status: ${GREEN}${HTTP_CODE}${NC}" >&2
    echo -e "  Latency: ${GREEN}${LATENCY} seconds${NC}" >&2
    echo -e "  Response Body:${MAGENTA}" >&2
    echo "$RESPONSE_BODY" | head -n 10 >&2 # Display up to 10 lines
    echo -e "${NC}" >&2
    
    # Use 'rm -f' to force removal and suppress 'No such file' errors
    rm -f "$TEMP_BODY_FILE" >&2
    
    # Echos the latency value to STDOUT so the calling script can capture it with $()
    echo "$LATENCY" 
    
    # Return MUST be a numeric value (the HTTP code)
    return "$HTTP_CODE" 
}
# --- End of Helper Function ---


echo -e "${BLUE}--- 1. Applying Kubernetes Deployment and Service ---${NC}"
kubectl apply -f deploy/kubernetes.yaml
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Failed to apply Kubernetes manifests.${NC}"
    exit 1
fi

echo -e "${YELLOW}Waiting 2 seconds for resource initialization...${NC}"
sleep 2s 

echo -e "${YELLOW}--- Waiting for Deployment ${DEPLOYMENT_NAME} to become ready ---${NC}"
kubectl -n "$NAMESPACE" rollout status deployment/"$DEPLOYMENT_NAME" --timeout=300s
if [ $? -ne 0 ]; then
    echo -e "${RED}ERROR: Deployment failed to become ready.${NC}"
    exit 1
fi

# --- 2. Initial Model Load Test (Warm-up) ---
echo -e "${BLUE}--- 2. Initial Warm-up Request (Logs redirected to /dev/null) ---${NC}"
# We call the function and send all its descriptive output to /dev/null
perform_curl_test "Warm-up" > /dev/null
WARMUP_CODE=$?

if [ "$WARMUP_CODE" -ne 200 ]; then
    echo -e "${RED}ERROR: Warm-up request failed. HTTP Status Code: $WARMUP_CODE${NC}"
    exit 1
fi
echo -e "${GREEN}Warm-up successful.${NC}"


# --- 3. First Performance Test (Baseline) ---
echo -e "${BLUE}--- 3. Baseline Performance Test (High Resource) ---${NC}"
# Capture the echoed latency using command substitution ($())
BASELINE_LATENCY=$(perform_curl_test "Baseline") 

# --- 4. Identifying Pod and Patch CPU Resources ---
echo -e "${BLUE}--- 4. Identifying Pod and Applying In-Place CPU Downscaling ---${NC}"

POD_NAME=$(kubectl -n "$NAMESPACE" get pods -l app="$DEPLOYMENT_NAME" -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
    echo -e "${RED}ERROR: Could not find a running Pod for deployment ${DEPLOYMENT_NAME}.${NC}"
    exit 1
fi

echo -e "Found Pod: ${YELLOW}${POD_NAME}${NC}. Applying CPU change to ${YELLOW}${NEW_CPU_LIMIT}${NC}..."

CONTAINER_NAME="measure-yolo-container" 
# Patching only limits for Burstable QOS
PATCH_CMD='{"spec":{"containers":[{"name":"'"${CONTAINER_NAME}"'", "resources":{"limits":{"cpu":"'"${NEW_CPU_LIMIT}"'"}}}]}}'

kubectl -n "$NAMESPACE" patch pod "$POD_NAME" --subresource resize --patch "$PATCH_CMD"

if [ $? -ne 0 ]; then
    echo -e "${YELLOW}WARNING: Patch command failed (QOS Class Issue). CPU resources were likely NOT changed.${NC}" 
fi

# echo -e "${YELLOW}Waiting 5 seconds for the resource change to take effect...${NC}"
# sleep 5 

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

kubectl delete -f deploy/kubernetes.yaml

echo -e "${GREEN}--- Script Finished ---${NC}"