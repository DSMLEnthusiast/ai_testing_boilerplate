using System.Diagnostics;
using System.Text.Json;
using Microsoft.Extensions.AI;

namespace MathMcp.MeaiEval;

public sealed record EvaluationResult(
    string RunId,
    string ScenarioId,
    string ModelProvider,
    string Response,
    IReadOnlyList<Dictionary<string, object?>> ToolCalls,
    bool Passed,
    string? FailureCategory,
    double LatencyMilliseconds,
    int RepetitionIndex);

public sealed record Scenario(
    string Id,
    string Prompt,
    string TargetBoundary,
    string RubricId,
    List<Dictionary<string, object>>? ExpectedTools = null,
    Dictionary<string, object>? Expected = null,
    string? ExpectedError = null,
    string? ExpectedResponseContains = null);

public sealed class MeaiEvaluator(IChatClient chatClient)
{
    public async Task<EvaluationResult> RunAsync(string scenarioId, string prompt, string modelProvider, int repetitionIndex, CancellationToken cancellationToken = default)
    {
        var started = Stopwatch.GetTimestamp();
        var response = await chatClient.GetResponseAsync(
            prompt,
            new ChatOptions { ModelId = Environment.GetEnvironmentVariable("MEAI_MODEL") ?? "gpt-4" },
            cancellationToken);
        var text = response.Text ?? string.Empty;
        var elapsed = Stopwatch.GetElapsedTime(started).TotalMilliseconds;

        return new EvaluationResult(
            RunId: $"meai-{scenarioId}-{repetitionIndex}",
            ScenarioId: scenarioId,
            ModelProvider: modelProvider,
            Response: text,
            ToolCalls: [],
            Passed: false, // Placeholder; real pass/fail logic depends on scenario type
            FailureCategory: null,
            LatencyMilliseconds: elapsed,
            RepetitionIndex: repetitionIndex);
    }
}

internal static class Program
{
    public static async Task Main(string[] args)
    {
        var parser = new ArgumentParser(args);
        var repetitions = parser.GetIntOption("--repetitions", 1);
        var output = parser.GetOption("--output", "results.json");
        var provider = parser.GetOption("--provider", "copilot-sdk");

        var scenarioPath = FindScenarioFile();
        if (!File.Exists(scenarioPath))
        {
            Console.Error.WriteLine($"ERROR: Scenarios file not found at {scenarioPath}");
            Environment.Exit(1);
        }

        var scenarioText = await File.ReadAllTextAsync(scenarioPath);
        var scenarios = JsonSerializer.Deserialize<List<Scenario>>(scenarioText);

        if (scenarios == null || scenarios.Count == 0)
        {
            Console.Error.WriteLine("ERROR: No scenarios loaded");
            Environment.Exit(1);
        }

        var results = new List<Dictionary<string, object>>();
        var agent = new CopilotSdkAgent();

        foreach (var repetition in Enumerable.Range(0, repetitions))
        {
            foreach (var scenario in scenarios)
            {
                try
                {
                    Console.WriteLine($"Running {scenario.Id} (repetition {repetition + 1}/{repetitions})...");

                    var result = await agent.RunAsync(scenario, CancellationToken.None);

                    var normalized = NormalizeResult(result, scenario, repetition, provider);
                    results.Add(normalized);

                    Console.WriteLine($"  -> {(result.Passed ? "PASS" : "FAIL")} ({result.LatencyMilliseconds:F2}ms)");
                }
                catch (Exception ex)
                {
                    Console.Error.WriteLine($"ERROR: {scenario.Id}: {ex.Message}");
                    results.Add(new Dictionary<string, object>
                    {
                        ["schema_version"] = "1.0",
                        ["run_id"] = $"meai-{scenario.Id}-{repetition}",
                        ["scenario_id"] = scenario.Id,
                        ["agent_runtime"] = "copilot-sdk-dotnet",
                        ["model_provider"] = provider,
                        ["repetition_index"] = repetition,
                        ["passed"] = false,
                        ["failure_category"] = "provider_error",
                        ["response"] = ex.Message,
                        ["latency_ms"] = 0.0
                    });
                }
            }
        }

        var json = JsonSerializer.Serialize(results, new JsonSerializerOptions { WriteIndented = true });
        await File.WriteAllTextAsync(output, json);
        Console.WriteLine($"Results written to {output}");
    }

    private static Dictionary<string, object> NormalizeResult(
        EvaluationResult result,
        Scenario scenario,
        int repetitionIndex,
        string provider)
    {
        return new Dictionary<string, object>
        {
            ["schema_version"] = "1.0",
            ["run_id"] = $"meai-{scenario.Id}-{repetitionIndex}",
            ["scenario_id"] = result.ScenarioId,
            ["agent_runtime"] = "copilot-sdk-dotnet",
            ["model_provider"] = provider,
            ["response"] = result.Response,
            ["tool_calls"] = result.ToolCalls,
            ["tool_results"] = result.ToolCalls
                .Where(call => call.ContainsKey("result"))
                .Select(call => call["result"])
                .ToList(),
            ["trace_status"] = result.ToolCalls.All(call =>
                call.ContainsKey("name") &&
                call.ContainsKey("arguments") &&
                call.ContainsKey("result"))
                ? "complete"
                : "partial",
            ["repetition_index"] = repetitionIndex,
            ["passed"] = result.Passed,
            ["failure_category"] = result.FailureCategory ?? "none",
            ["latency_ms"] = result.LatencyMilliseconds,
            ["target_boundary"] = scenario.TargetBoundary,
            ["rubric_id"] = scenario.RubricId
        };
    }

    private static string FindScenarioFile()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory != null)
        {
            var scenarioPath = Path.Combine(directory.FullName, "evals", "golden", "scenarios.json");
            if (File.Exists(scenarioPath))
            {
                return scenarioPath;
            }
            directory = directory.Parent;
        }
        return Path.Combine(Environment.CurrentDirectory, "evals", "golden", "scenarios.json");
    }
}

/// <summary>
/// Simple command-line argument parser for convenience.
/// </summary>
internal class ArgumentParser
{
    private readonly Dictionary<string, string> _args = new();

    public ArgumentParser(string[] args)
    {
        for (int i = 0; i < args.Length; i++)
        {
            if (args[i].StartsWith("--"))
            {
                var key = args[i];
                var value = (i + 1 < args.Length && !args[i + 1].StartsWith("--")) ? args[++i] : "true";
                _args[key] = value;
            }
        }
    }

    public string GetOption(string key, string defaultValue = "")
    {
        return _args.TryGetValue(key, out var value) ? value : defaultValue;
    }

    public int GetIntOption(string key, int defaultValue = 0)
    {
        return _args.TryGetValue(key, out var value) && int.TryParse(value, out var intValue) ? intValue : defaultValue;
    }
}
