. .env

case "${MCP_URL}" in
  http://*|https://*) MCP_ENDPOINT="${MCP_URL%/}/mcp" ;;
  *) MCP_ENDPOINT="https://${MCP_URL%/}/mcp" ;;
esac

claude mcp add --transport http worldcat "${MCP_ENDPOINT}"
