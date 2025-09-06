#!/bin/bash

# Check for the primary command 'hpa'
if [[ "$1" == "vpa" ]]; then
    echo "Adjusting VPA configuration..."

    # Check to ensure all required arguments ($2, $3, $4) are provided
    if [[ -z "$2" || -z "$3" || -z "$4" ]]; then
        echo "Error: Missing arguments."
        echo "Usage: $0 vpa <pod-name> <cpu-request> <cpu-limit>"
        exit 1
    fi

    # Use variables in the command. Note the patch string is now in
    # double quotes (") to allow variables like "$3" and "$4" to be expanded.
    kubectl patch pod "$2" --subresource resize --patch \
    "{\"spec\":{\"containers\":[{\"name\":\"sampleapp\", \"resources\":{\"requests\":{\"cpu\":\"$3\"}, \"limits\":{\"cpu\":\"$4\"}}}]}}"

    # Check if the patch command was successful
    if [[ $? -eq 0 ]]; then
        echo "Successfully patched pod '$2' with CPU request '$3' and limit '$4'."
    else
        echo "Failed to patch pod '$2'."
    fi
fi