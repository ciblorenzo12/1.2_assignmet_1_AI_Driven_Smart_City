using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using UnityEngine;
using TMPro;
public class EnergyReplayManager : MonoBehaviour
{
    [Header("CSV in Assets/StreamingAssets")]
    public string energyCsvFileName = "energy_zones_log_forecast.csv";
    public float playbackSpeed = 1.0f;

    [Header("UI Texts (assign)")]
  public TMP_Text tText;
public TMP_Text reqText;
public TMP_Text servedText;
public TMP_Text unmetText;
public TMP_Text predText;

    private List<Dictionary<string, string>> rows = new();
    private Dictionary<string, int> colIndex = new();

    private int rowIdx = 0;
    private float simClock = 0f;

    void Start()
    {
        LoadCsvFromStreamingAssets(energyCsvFileName);
        if (rows.Count == 0) { enabled = false; return; }

        // Some energy logs use t_s instead of t
        simClock = GetTime(rows[0]);
        ApplyRow(0);
    }

    void Update()
    {
        simClock += Time.deltaTime * playbackSpeed;

        while (rowIdx + 1 < rows.Count)
        {
            float nextT = GetTime(rows[rowIdx + 1]);
            if (nextT > simClock) break;
            rowIdx++;
        }

        ApplyRow(rowIdx);
    }

    private void ApplyRow(int i)
    {
        var r = rows[i];
        float t = GetTime(r);

        tText.text = $"t={t:0}s";

        // Your energy CSV columns:
        // total_req_kw, total_served_kw, total_unmet_kw, (optional) pred_next_total_req_kw
        reqText.text = $"Total Request (kW): {GetF(r, "total_req_kw"):0.0}";
        servedText.text = $"Total Served (kW): {GetF(r, "total_served_kw"):0.0}";
        unmetText.text = $"Total Unmet (kW): {GetF(r, "total_unmet_kw"):0.0}";

        if (predText != null)
{
        if (r.ContainsKey("pred_next_total_req_kw") && !string.IsNullOrEmpty(r["pred_next_total_req_kw"]))
            predText.text = $"Pred Next Req (kW): {GetF(r, "pred_next_total_req_kw"):0.0}";
        else
            predText.text = ""; // hide line on baseline
}
    }

    private float GetTime(Dictionary<string, string> r)
    {
        if (r.ContainsKey("t_s")) return ParseFloat(r["t_s"]);
        if (r.ContainsKey("t")) return ParseFloat(r["t"]);
        return 0f;
    }

    private float GetF(Dictionary<string, string> r, string key)
    {
        if (!r.ContainsKey(key)) return 0f;
        return ParseFloat(r[key]);
    }

    private void LoadCsvFromStreamingAssets(string fileName)
    {
        string path = Path.Combine(Application.streamingAssetsPath, fileName);
        Debug.Log("Loading Energy CSV: " + path);

        if (!File.Exists(path))
        {
            Debug.LogError("Energy CSV not found: " + path);
            return;
        }

        string[] lines = File.ReadAllLines(path);
        if (lines.Length < 2) return;

        string[] headers = lines[0].Split(',');
        for (int c = 0; c < headers.Length; c++)
            colIndex[headers[c]] = c;

        for (int i = 1; i < lines.Length; i++)
        {
            if (string.IsNullOrWhiteSpace(lines[i])) continue;
            string[] cells = lines[i].Split(',');

            var row = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
            foreach (var kv in colIndex)
            {
                int idx = kv.Value;
                row[kv.Key] = (idx < cells.Length) ? cells[idx] : "";
            }
            rows.Add(row);
        }
    }

    private float ParseFloat(string s)
    {
        if (float.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out float v)) return v;
        return 0f;
    }
    public void LoadEnergyFile(string fileName)
    {
        energyCsvFileName = fileName;

        rows.Clear();
        colIndex.Clear();
        rowIdx = 0;
        simClock = 0f;

        LoadCsvFromStreamingAssets(energyCsvFileName);

        if (rows.Count > 0)
        {
            simClock = GetTime(rows[0]);
            ApplyRow(0);
        }
    }
}