using System.Diagnostics;
using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;
using GitHub.Copilot;
using GitHub.Copilot.Rpc;

namespace MathMcp.MeaiEval;

/// <summary>
/// Copilot SDK agent that runs scenarios with MCP tool integration.
/// Captures agent messages, tool calls, session lifecycle, and evaluation metrics.
/// </summary>
public sealed class CopilotSdkAgent
{
    private static readonly HashSet<string> AllowedMathTools =
    [
        "add",
        "subtract",
        "multiply",
        "divide",
        "power",
        "exp",
        "log"
    ];

#pragma warning disable GHCP001
    private static Task<PermissionDecision> HandlePermissionRequestAsync(
        PermissionRequest request,
        PermissionInvocation _)
    {
        if (request is PermissionRequestMcp mcpRequest &&
            string.Equals(mcpRequest.ServerName, "math-mcp", StringComparison.Ordinal) &&
            AllowedMathTools.Contains(mcpRequest.ToolName))
        {
            return Task.FromResult(PermissionDecision.ApproveOnce());
        }

        return Task.FromResult(PermissionDecision.Reject("Only registered math MCP tools are allowed."));
    }
#pragma warning restore GHCP001

    public async Task<EvaluationResult> RunAsync(
        Scenario scenario,
        CancellationToken cancellationToken = default)
    {
        var root = FindRepositoryRoot();
        var started = Stopwatch.GetTimestamp();
        var toolCallsById = new Dictionary<string, Dictionary<string, object?>>(StringComparer.OrdinalIgnoreCase);
        var toolCallOrder = new List<Dictionary<string, object?>>();
        var passed = false;
        var responseText = string.Empty;

        try
        {
            await using var client = new CopilotClient();
            await client.StartAsync();

            await using var session = await client.CreateSessionAsync(new SessionConfig
            {
                Model = Environment.GetEnvironmentVariable("COPILOT_MODEL") ?? "gpt-4.1",
                OnPermissionRequest = HandlePermissionRequestAsync,
                McpServers = new Dictionary<string, McpServerConfig>
                {
                    ["math-mcp"] = new McpStdioServerConfig
                    {
                        Command = Environment.GetEnvironmentVariable("PYTHON") ?? "python",
                        Args = ["-m", "mcp_app.server"],
                        Env = new Dictionary<string, string>
                        {
                            ["PYTHONPATH"] = Path.Combine(root, "src")
                        },
                        Tools = ["*"],
                        Timeout = 30000
                    }
                }
            });

            using var subscription = session.On<SessionEvent>(sessionEvent =>
            {
                switch (sessionEvent)
                {
                    case ToolExecutionStartEvent startedEvent:
                        var startedData = startedEvent.Data;
                        if (string.IsNullOrWhiteSpace(startedData.ToolCallId))
                        {
                            break;
                        }

                        if (!toolCallsById.TryGetValue(startedData.ToolCallId, out var toolCall))
                        {
                            toolCall = new Dictionary<string, object?>();
                            toolCallsById[startedData.ToolCallId] = toolCall;
                            toolCallOrder.Add(toolCall);
                        }

                        toolCall["event_id"] = startedData.ToolCallId;
                        toolCall["name"] = startedData.McpToolName ?? startedData.ToolName;
                        toolCall["arguments"] = startedData.Arguments;
                        toolCall["mcp_server"] = startedData.McpServerName;
                        break;
                    case ToolExecutionCompleteEvent completedEvent:
                        var completedData = completedEvent.Data;
                        if (string.IsNullOrWhiteSpace(completedData.ToolCallId))
                        {
                            break;
                        }

                        if (!toolCallsById.TryGetValue(completedData.ToolCallId, out var completedToolCall))
                        {
                            completedToolCall = new Dictionary<string, object?>
                            {
                                ["event_id"] = completedData.ToolCallId
                            };
                            toolCallsById[completedData.ToolCallId] = completedToolCall;
                            toolCallOrder.Add(completedToolCall);
                        }

                        completedToolCall["result"] = completedData.Result;
                        completedToolCall["success"] = completedData.Success;
                        completedToolCall["error"] = completedData.Error?.Message;
                        break;
                }
            });

            var response = await session.SendAndWaitAsync(new MessageOptions { Prompt = scenario.Prompt });
            responseText = ExtractResponseText(response);

            var failureCategory = ScenarioAssertions.GetFailureCategory(scenario, responseText, toolCallOrder);
            passed = failureCategory is null;

            var elapsed = Stopwatch.GetElapsedTime(started).TotalMilliseconds;
            return new EvaluationResult(
                RunId: $"copilot-{scenario.Id}",
                ScenarioId: scenario.Id,
                ModelProvider: "github-copilot-sdk",
                Response: responseText,
                ToolCalls: toolCallOrder,
                Passed: passed,
                FailureCategory: failureCategory,
                LatencyMilliseconds: elapsed,
                RepetitionIndex: 0);
        }
        catch (Exception ex)
        {
            var elapsed = Stopwatch.GetElapsedTime(started).TotalMilliseconds;
            return new EvaluationResult(
                RunId: $"copilot-{scenario.Id}",
                ScenarioId: scenario.Id,
                ModelProvider: "github-copilot-sdk",
                Response: $"Error: {ex.Message}",
                ToolCalls: toolCallOrder,
                Passed: false,
                FailureCategory: "provider_error",
                LatencyMilliseconds: elapsed,
                RepetitionIndex: 0);
        }
    }

    private static string ExtractResponseText(object? response)
    {
        if (response is null)
        {
            return string.Empty;
        }

        foreach (var candidate in new[] { response, GetPropertyValue(response, "Data") })
        {
            if (candidate is null)
            {
                continue;
            }

            foreach (var propertyName in new[] { "Content", "Text", "Output" })
            {
                var value = GetPropertyValue(candidate, propertyName);
                if (value is string text && !string.IsNullOrWhiteSpace(text))
                {
                    return text;
                }
            }
        }

        return response.ToString() ?? string.Empty;
    }

    private static object? GetPropertyValue(object? instance, string propertyName)
    {
        return instance?.GetType().GetProperty(propertyName)?.GetValue(instance);
    }

    /// <summary>
    /// Locates the repository root by searching for pyproject.toml file.
    /// </summary>
    private static string FindRepositoryRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory is not null && !File.Exists(Path.Combine(directory.FullName, "pyproject.toml")))
        {
            directory = directory.Parent;
        }

        return directory?.FullName ?? Environment.CurrentDirectory;
    }
}

