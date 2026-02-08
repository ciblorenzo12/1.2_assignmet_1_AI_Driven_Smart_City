using UnityEngine;
using TMPro;

public class TrafficModeDropdownController : MonoBehaviour
{
    public TMP_Dropdown dropdown;
    public TMP_Text statusText;
    public CityReplayManager city;

    void Start()
    {
        if (dropdown == null || city == null) return;
        dropdown.onValueChanged.AddListener(OnChanged);
        OnChanged(dropdown.value);
    }

    void OnChanged(int idx)
    {
        if (idx == 0)
            city.LoadTrafficFile("grid_2x2_snapshots_fixed.csv");
        else if (idx == 1)
            city.LoadTrafficFile("grid_2x2_snapshots_actuated.csv");
        else
            city.LoadTrafficFile("grid_2x2_snapshots_dt.csv");

        if (statusText != null)
            statusText.text = $"Traffic File: {city.loadedTrafficFile} (rows={city.loadedTrafficRows})";
    }
}
