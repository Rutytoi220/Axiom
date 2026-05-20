"""Example: Creating a custom tool."""

from axiom import BaseTool, ToolResult, ToolParameter
from axiom import Engine


class CalculatorTool(BaseTool):
    """Simple calculator tool."""
    
    def __init__(self):
        super().__init__(
            tool_id="calculator",
            name="Calculator",
            description="Perform basic arithmetic calculations"
        )
        self.add_parameter(ToolParameter(
            name="expression",
            type="string",
            description="Mathematical expression (e.g., '2+2')",
            required=True
        ))
    
    def execute(self, expression: str, **kwargs) -> ToolResult:
        """Execute calculator."""
        try:
            # Safe evaluation for math expressions
            result = eval(expression, {"__builtins__": {}})
            return ToolResult(
                success=True,
                output={
                    "expression": expression,
                    "result": result
                }
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=None,
                error=f"Invalid expression: {e}"
            )


def main():
    """Register and test custom tool."""
    
    engine = Engine()
    engine.initialize()
    
    # Create and register custom tool
    calc = CalculatorTool()
    engine.registry.register_tool(calc.tool_id, calc)
    
    print("Custom Tool Example")
    print("=" * 60)
    
    # List registered tools
    tools = engine.registry.list_tools()
    print(f"\nRegistered {len(tools)} tool(s):")
    for tool_id, tool in tools.items():
        print(f"  - {tool.name} ({tool_id})")
    
    # Execute the tool
    print("\nTesting calculator tool:")
    result = calc(expression="2 + 2 * 3")
    print(f"  Input: 2 + 2 * 3")
    print(f"  Result: {result.output}")
    
    # Get tool info
    print("\nTool Info:")
    info = calc.get_info()
    print(f"  Name: {info['name']}")
    print(f"  Description: {info['description']}")
    print(f"  Parameters: {len(info['parameters'])}")
    print(f"  Executions: {info['execution_count']}")
    
    engine.shutdown()
    print("\nExample complete!")


if __name__ == "__main__":
    main()
