using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
using UnityEngine.UI;

public class CityReplayManager : MonoBehaviour
{
    public string loadedTrafficFile = "";
    public int loadedTrafficRows = 0;

    [Header("CSV in Assets/StreamingAssets")]
    public string trafficCsvFileName = "grid_2x2_snapshots.csv";
    public float playbackSpeed = 1.0f; // sim seconds per real second

    [Header("Assign Intersections (A/B/C/D)")]
    public IntersectionViz A;
    public IntersectionViz B;
    public IntersectionViz C;
    public IntersectionViz D;

    [Header("Optional UI")]
    public Text infoText;

    private List<Dictionary<string, string>> rows = new();
    private Dictionary<string, int> colIndex = new();

    private int rowIdx = 0;
    private float simClock = 0f;

    void Start()
    {
        LoadCsvFromStreamingAssets(trafficCsvFileName);

        if (rows.Count == 0)
        {
            Debug.LogError("No CSV rows loaded. Check StreamingAssets file name/path.");
            enabled = false;
            return;
        }

        // Start at first timestamp
        simClock = ParseFloat(rows[0]["t"]);
        ApplyRow(0);
    }

    void Update()
    {
        simClock += Time.deltaTime * playbackSpeed;

        // advance to the latest row whose t <= simClock
        while (rowIdx + 1 < rows.Count)
        {
            float nextT = ParseFloat(rows[rowIdx + 1]["t"]);
            if (nextT > simClock) break;
            rowIdx++;
        }

        ApplyRow(rowIdx);

        if (infoText != null)
        {
            infoText.text = $"t={ParseFloat(rows[rowIdx]["t"]):0.0}s | row={rowIdx}/{rows.Count - 1}";
        }
    }

    private void ApplyRow(int i)
    {
        var r = rows[i];

        ApplyIntersection(A, r, "A");
        ApplyIntersection(B, r, "B");
        ApplyIntersection(C, r, "C");
        ApplyIntersection(D, r, "D");
    }

    private void ApplyIntersection(IntersectionViz viz, Dictionary<string, string> r, string name)
    {
        if (viz == null) return;

        int qNs = ParseInt(r[$"{name}_q_ns"]);
        int qEw = ParseInt(r[$"{name}_q_ew"]);
        string phase = r[$"{name}_phase"];

        viz.ApplyState(qNs, qEw, phase);
    }

    private void LoadCsvFromStreamingAssets(string fileName)
    {
        string path = Path.Combine(Application.streamingAssetsPath, fileName);
        Debug.Log("Loading CSV: " + path);

        if (!File.Exists(path))
        {
            Debug.LogError("CSV not found: " + path);
            return;
        }

        string[] lines = File.ReadAllLines(path);
        if (lines.Length < 2) return;

        string[] headers = SplitCsvLine(lines[0]);
        for (int c = 0; c < headers.Length; c++)
            colIndex[headers[c]] = c;

        for (int i = 1; i < lines.Length; i++)
        {
            if (string.IsNullOrWhiteSpace(lines[i])) continue;
            string[] cells = SplitCsvLine(lines[i]);

            var row = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var kv in colIndex)
            {
                int idx = kv.Value;
                row[kv.Key] = (idx < cells.Length) ? cells[idx] : "";
            }
            rows.Add(row);
        }
        loadedTrafficFile = trafficCsvFileName;
        loadedTrafficRows = rows.Count;
        Debug.Log($"Loaded Traffic CSV: {loadedTrafficFile} | rows={loadedTrafficRows}");
    }

    // Minimal CSV split (works for your numeric CSVs; no quoted commas expected)
    private string[] SplitCsvLine(string line) => line.Split(',');

    private int ParseInt(string s)
    {
        if (int.TryParse(s, NumberStyles.Integer, CultureInfo.InvariantCulture, out int v)) return v;
        return 0;
    }

    private float ParseFloat(string s)
    {
        if (float.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out float v)) return v;
        return 0f;
    }

    public void LoadTrafficFile(string fileName)
    {
        trafficCsvFileName = fileName;

        rows.Clear();
        colIndex.Clear();
        rowIdx = 0;
        simClock = 0f;

        LoadCsvFromStreamingAssets(trafficCsvFileName);

        if (rows.Count > 0)
        {
            simClock = ParseFloat(rows[0]["t"]);
            ApplyRow(0);
        }
    }

}