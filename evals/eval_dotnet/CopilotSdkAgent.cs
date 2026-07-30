using System.Diagnostics;
using System.Text.Json;
using GitHub.Copilot;

namespace MathMcp.MeaiEval;

/// <summary>
/// Copilot SDK agent that runs scenarios with MCP tool integration.
/// Captures agent messages, tool calls, session lifecycle, and evaluation metrics.
/// </summary>
public sealed class CopilotSdkAgent
{
    public async Task<EvaluationResult> RunAsync(
        Scenario scenario,
        CancellationToken cancellationToken = default)
    {
        var root = FindRepositoryRoot();
        var started = Stopwatch.GetTimestamp();
        var toolCalls = new List<string>();
        var passed = false;

        try
        {
            await using var client = new CopilotClient();
            await client.StartAsync();

            await using var session = await client.CreateSessionAsync(new SessionConfig
            {
                Model = Environment.GetEnvironmentVariable("COPILOT_MODEL") ?? "gpt-4.1",
                OnPermissionRequest = PermissionHandler.ApproveAll,
                McpServers = new Dictionary<string, McpServerConfig>
                {
                    ["math-mcp"] = new McpStdioServerConfig
                    {
                        // Use Python executable from environment or default to "python"
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

            var response = await session.SendAndWaitAsync(new MessageOptions { Prompt = scenario.Prompt });
            var text = response?.Data.Content ?? string.Empty;

            var failureCategory = ScenarioAssertions.GetFailureCategory(scenario, text);
            passed = failureCategory is null;

            var elapsed = Stopwatch.GetElapsedTime(started).TotalMilliseconds;
            return new EvaluationResult(
                RunId: $"copilot-{scenario.Id}",
                ScenarioId: scenario.Id,
                ModelProvider: "github-copilot-sdk",
                Response: text,
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
                Passed: false,
                FailureCategory: "provider_error",
                LatencyMilliseconds: elapsed,
                RepetitionIndex: 0);
        }
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

internal static class ScenarioAssertions
{
    public static string? GetFailureCategory(Scenario scenario, string response)
    {
        if (!string.IsNullOrWhiteSpace(scenario.ExpectedError))
        {
            return ContainsError(response, scenario.ExpectedError)
                ? null
                : "expected_error_not_reported";
        }

        if (!string.IsNullOrWhiteSpace(scenario.ExpectedResponseContains) &&
            !response.Contains(scenario.ExpectedResponseContains, StringComparison.OrdinalIgnoreCase))
        {
            return "expected_response_not_found";
        }

        if (scenario.Expected is not null && scenario.Expected.TryGetValue("value", out var value))
        {
            var expected = value is JsonElement element
                ? element.GetDouble().ToString(System.Globalization.CultureInfo.InvariantCulture)
                : Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture);
            if (expected is null || !ContainsNumber(response, expected))
            {
                return "expected_value_not_found";
            }
        }

        return null;
    }

    private static bool ContainsError(string response, string category)
    {
        if (response.Contains(category, StringComparison.OrdinalIgnoreCase)) return true;
        var phrase = category switch
        {
            "division_by_zero" => "divide by zero",
            "domain_error" => "domain",
            "non_finite_result" => "overflow",
            "invalid_arguments" => "invalid argument",
            _ => category
        };
        return response.Contains(phrase, StringComparison.OrdinalIgnoreCase);
    }

    private static bool ContainsNumber(string response, string expected)
    {
        var normalized = expected.TrimEnd('0').TrimEnd('.');
        return response.Contains(expected, StringComparison.Ordinal) ||
               (normalized.Length > 0 && response.Contains(normalized, StringComparison.Ordinal));
    }
}
