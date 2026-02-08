using UnityEngine;
using TMPro;

public class EnergyModeDropdownController : MonoBehaviour
{
    public TMP_Dropdown dropdown;
    public EnergyReplayManager energy;

    void Start()
    {
        if (dropdown == null || energy == null) return;

        dropdown.onValueChanged.AddListener(OnChanged);

        // Initialize with the current selection
        OnChanged(dropdown.value);
    }

    void OnChanged(int idx)
    {
        if (idx == 0)
            energy.LoadEnergyFile("energy_zones_log.csv");
        else
            energy.LoadEnergyFile("energy_zones_log_forecast.csv");
    }
}