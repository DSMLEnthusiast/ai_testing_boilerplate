using System.Globalization;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace MathMcp.MeaiEval;

internal static partial class ScenarioAssertions
{
    public static string? GetFailureCategory(
        Scenario scenario,
        string response,
        IReadOnlyList<Dictionary<string, object?>> toolCalls)
    {
        if (!string.IsNullOrWhiteSpace(scenario.ExpectedError))
        {
            return ContainsError(response, scenario.ExpectedError)
                ? null
                : "expected_error_not_reported";
        }

        if (!string.IsNullOrWhiteSpace(scenario.ExpectedResponse))
        {
            return ContainsResponse(response, scenario.ExpectedResponse)
                ? null
                : "expected_response_not_found";
        }

        if (!string.IsNullOrWhiteSpace(scenario.ExpectedResponseContains) &&
            !ContainsResponse(response, scenario.ExpectedResponseContains))
        {
            return "expected_response_not_found";
        }

        if (scenario.ExpectedTools is { Count: > 0 } expectedTools &&
            !ToolCallsMatchExpectation(expectedTools, toolCalls))
        {
            return "expected_tools_not_found";
        }

        if (scenario.Expected is not null && scenario.Expected.TryGetValue("value", out var value))
        {
            var expected = value is JsonElement element
                ? element.ToString()
                : Convert.ToString(value, CultureInfo.InvariantCulture);
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

    private static bool ContainsResponse(string response, string expected)
    {
        return response.Contains(expected, StringComparison.OrdinalIgnoreCase);
    }

    private static bool ContainsNumber(string response, string expected)
    {
        if (!double.TryParse(expected, NumberStyles.Float, CultureInfo.InvariantCulture, out var expectedValue))
        {
            return false;
        }

        foreach (Match match in NumberPattern().Matches(response))
        {
            if (!double.TryParse(match.Value, NumberStyles.Float, CultureInfo.InvariantCulture, out var actualValue))
            {
                continue;
            }

            var tolerance = 1e-9 * Math.Max(1.0, Math.Max(Math.Abs(expectedValue), Math.Abs(actualValue)));
            if (Math.Abs(expectedValue - actualValue) <= tolerance)
            {
                return true;
            }
        }

        return false;
    }

    private static bool ToolCallsMatchExpectation(
        IReadOnlyList<Dictionary<string, object?>> expectedTools,
        IReadOnlyList<Dictionary<string, object?>> actualCalls)
    {
        if (expectedTools.Count != actualCalls.Count)
        {
            return false;
        }

        for (var index = 0; index < expectedTools.Count; index++)
        {
            var expected = expectedTools[index];
            var actual = actualCalls[index];

            var expectedName = GetStringValue(expected, "name");
            var actualName = GetStringValue(actual, "name");
            if (expectedName is null || actualName is null ||
                !string.Equals(expectedName, actualName, StringComparison.OrdinalIgnoreCase))
            {
                return false;
            }

            var expectedArguments = SerializeArguments(expected.GetValueOrDefault("arguments"));
            var actualArguments = SerializeArguments(actual.GetValueOrDefault("arguments"));
            if (!string.Equals(expectedArguments, actualArguments, StringComparison.Ordinal))
            {
                return false;
            }
        }

        return true;
    }

    private static string? GetStringValue(IReadOnlyDictionary<string, object?> values, string key)
    {
        if (values.TryGetValue(key, out var value) && value is string text && !string.IsNullOrWhiteSpace(text))
        {
            return text;
        }

        return null;
    }

    private static string SerializeArguments(object? value)
    {
        if (value is null)
        {
            return "{}";
        }

        if (value is JsonElement element)
        {
            return element.GetRawText();
        }

        return JsonSerializer.Serialize(value);
    }

    [GeneratedRegex(@"(?<![\w.])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?![\w.])")]
    private static partial Regex NumberPattern();
}
