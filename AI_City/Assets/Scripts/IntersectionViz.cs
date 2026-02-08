using UnityEngine;

public class IntersectionViz : MonoBehaviour
{
    [Header("Assign in Inspector")]
    public Transform nsBar;
    public Transform ewBar;
    public Renderer nsRenderer;
    public Renderer ewRenderer;

    [Header("Tuning")]
    public float maxBarHeight = 3.0f;
    public int maxQueueForScale = 30;

    public void ApplyState(int qNs, int qEw, string phase)
    {
        // Scale bars by queue sizes
        float nsH = Mathf.Clamp01(qNs / (float)maxQueueForScale) * maxBarHeight;
        float ewH = Mathf.Clamp01(qEw / (float)maxQueueForScale) * maxBarHeight;

        SetBarHeight(nsBar, nsH);
        SetBarHeight(ewBar, ewH);

        // Phase coloring (no transparency needed)
        bool nsGreen = (phase == "NS");
        nsRenderer.material.color = nsGreen ? Color.green : Color.gray;
        ewRenderer.material.color = nsGreen ? Color.gray : Color.green;
    }

    private void SetBarHeight(Transform bar, float h)
    {
        // keep a minimum visible height
        float height = Mathf.Max(0.1f, h);

        Vector3 s = bar.localScale;
        s.y = height;
        bar.localScale = s;

        // keep bottom on the ground by moving up half the height
        Vector3 p = bar.localPosition;
        p.y = height / 2.0f;
        bar.localPosition = p;
    }
}