
import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_mcp_client_demo():
    print("="*60)
    print("TASKFLOW REAL-WORLD MCP CONNECTION")
    print("="*60)

    # Configure the server parameters (connecting via stdio to the server script)
    server_params = StdioServerParameters(
        command="python",
        args=["src/mcp_server.py"],
        env=None
    )

    print("\n[1] Connecting to MCP Server via stdio...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()
            print("Successfully connected and initialized session.")

            # List available tools
            print("\n[2] Fetching available tools from MCP Server...")
            tools = await session.list_tools()
            for tool in tools.tools:
                print(f" - Tool Found: {tool.name}")

            # Call a tool: search_knowledge_base
            print("\n[3] Calling 'search_knowledge_base' via MCP Protocol...")
            query = "How do I reset my password?"
            result = await session.call_tool("search_knowledge_base", arguments={"query": query})
            
            print(f"Query: '{query}'")
            print("Result from MCP Server:")
            print("-" * 40)
            # The result content is usually a list of TextContent objects
            for content in result.content:
                if hasattr(content, 'text'):
                    # Parse JSON if the tool returns a JSON string
                    try:
                        parsed = json.loads(content.text)
                        print(json.dumps(parsed, indent=2))
                    except:
                        print(content.text)
            print("-" * 40)

            # Create a ticket via MCP
            print("\n[4] Creating a 'real world' ticket via MCP Protocol...")
            ticket_args = {
                "customer_name": "MCP RealWorld Tester",
                "message": "Connecting Gmail and WhatsApp via MCP protocol.",
                "channel": "email",
                "email": "mcp.tester@example.com"
            }
            ticket_result = await session.call_tool("create_ticket", arguments=ticket_args)
            print("Ticket Creation Result:")
            for content in ticket_result.content:
                print(content.text if hasattr(content, 'text') else content)

    print("\n" + "="*60)
    print("MCP CONNECTION DEMO COMPLETE")
    print("="*60)

if __name__ == "__main__":
    asyncio.run(run_mcp_client_demo())
