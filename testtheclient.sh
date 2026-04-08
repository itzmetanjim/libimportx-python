#!/bin/bash
# this one test is writtn by AI
SOCKET="/tmp/libx.sock"
TOKEN="mytoken"
CLIENT_FILE="testclient.py"
LOG="results.log"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

echo "--- Starting libimportx Automation Test ---"

# 1. Cleanup
rm -f "$SOCKET" "$LOG"

# 2. Start the Listener
# The Host (Bash) sends "+" to approve the connection, then sends commands.
(
    # Send the approval (handshake)
    echo "+"
    # Send the commands
    echo '{"type": "read", "identifier": "variable"}'
    echo '{"type": "read", "identifier": "mydict.key"}'
    echo '{"type": "read", "identifier": "myfunction"}'
    echo '{"type": "call", "identifier": "myfunction"}'
    echo '{"type": "call", "identifier": "json.dumps", "args": [{"a": 1}]}'
    # Keep the pipe open for 2 seconds so we can catch the responses
    sleep 2
) | socat UNIX-LISTEN:"$SOCKET",reuseaddr - > "$LOG" 2>&1 &
SOCAT_PID=$!

# 3. Start Python Guest
export LIBIMPORTX=true
export LIBIMPORTX_HOST=$SOCKET
export LIBIMPORTX_TOKEN=$TOKEN
export PYTHONPATH="."

# Give socat a moment to start listening
sleep 0.5

# Run the guest
python3 "$CLIENT_FILE" &
PY_PID=$!

# 4. Wait for completion
echo "Running tests..."
sleep 3

echo -e "\n--- Verification ---"

# Useful for debugging:
# echo "--- RAW LOG CONTENT ---"
# cat "$LOG"
# echo "-----------------------"

check() {
    # -F means "Fixed String" (no regex/escape interpretation)
    # -q means "Quiet"
    if grep -Fq "$1" "$LOG"; then
        echo -e "${GREEN}PASS: $2${NC}"
    else
        echo -e "${RED}FAIL: $2${NC}"
        echo "      Expected literal string: $1"
        # Debug: Show what was actually in the log
        echo "      Actual log contains: $(grep 'call' "$LOG" | tail -n 1)"
        return 1
    fi
}

check '+"value"' "Read string variable"
check '+"value"' "Read dictionary key"
check '"__libimportx_foreign_type__": "function"' "Function handle"
check '+true' "Function call execution"
check '+"{\"a\": 1}"' "json.dumps logic"

# 5. Cleanup
kill $PY_PID $SOCAT_PID 2>/dev/null
rm -f "$SOCKET" "$LOG"
echo "Test Suite Complete."
