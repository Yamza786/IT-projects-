"""Fit a line with batch gradient descent and save a prediction plot."""

from pathlib import Path

import numpy as np


def fit_linear_regression(x: np.ndarray, y: np.ndarray, *, learning_rate: float = 0.01,
                          epochs: int = 1_000) -> tuple[float, float]:
    """Return slope and intercept fitted with batch gradient descent."""
    if x.ndim != 1 or y.ndim != 1 or x.size != y.size or x.size == 0:
        raise ValueError("x and y must be non-empty one-dimensional arrays of equal length")

    slope = 0.0
    intercept = 0.0
    for _ in range(epochs):
        predictions = slope * x + intercept
        errors = predictions - y
        slope -= learning_rate * np.mean(errors * x)
        intercept -= learning_rate * np.mean(errors)
    return slope, intercept


def main() -> None:
    # Deterministic sample data: y is approximately 2.5x + 4.
    x = np.arange(0.0, 10.0, 1.0)
    y = np.array([4.2, 6.1, 8.8, 11.2, 13.7, 16.3, 18.4, 21.1, 23.8, 26.2])
    slope, intercept = fit_linear_regression(x, y)
    predictions = slope * x + intercept

    output_path = Path(__file__).with_name("linear_regression_predictions.svg")
    width, height, margin = 720, 480, 55
    x_min, x_max = float(x.min()), float(x.max())
    y_min, y_max = float(min(y.min(), predictions.min())), float(max(y.max(), predictions.max()))
    y_padding = (y_max - y_min) * 0.1
    y_min -= y_padding
    y_max += y_padding

    def point(x_value: float, y_value: float) -> tuple[float, float]:
        px = margin + (x_value - x_min) / (x_max - x_min) * (width - 2 * margin)
        py = height - margin - (y_value - y_min) / (y_max - y_min) * (height - 2 * margin)
        return px, py

    observed = "\n".join(
        f'<circle cx="{point(float(xv), float(yv))[0]:.1f}" '
        f'cy="{point(float(xv), float(yv))[1]:.1f}" r="5" fill="#4682b4"/>'
        for xv, yv in zip(x, y)
    )
    fitted = " ".join(
        f"{px:.1f},{py:.1f}"
        for px, py in (point(float(xv), float(yv)) for xv, yv in zip(x, predictions))
    )
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
<rect width="100%" height="100%" fill="white"/>
<text x="{width / 2}" y="28" text-anchor="middle" font-family="sans-serif" font-size="18">Linear regression with gradient descent</text>
<line x1="{margin}" y1="{height - margin}" x2="{width - margin}" y2="{height - margin}" stroke="#333"/>
<line x1="{margin}" y1="{margin}" x2="{margin}" y2="{height - margin}" stroke="#333"/>
<polyline points="{fitted}" fill="none" stroke="#e87924" stroke-width="3"/>
{observed}
<text x="{width / 2}" y="{height - 12}" text-anchor="middle" font-family="sans-serif">x</text>
<text x="18" y="{height / 2}" text-anchor="middle" font-family="sans-serif" transform="rotate(-90 18 {height / 2})">y</text>
<text x="{margin + 8}" y="{margin + 15}" font-family="sans-serif" font-size="13" fill="#4682b4">Observed data</text>
<text x="{margin + 8}" y="{margin + 33}" font-family="sans-serif" font-size="13" fill="#e87924">Fit: y = {slope:.2f}x + {intercept:.2f}</text>
</svg>
'''
    output_path.write_text(svg, encoding="utf-8")
    print(f"Fitted line: y = {slope:.3f}x + {intercept:.3f}")
    print(f"Prediction plot saved to {output_path}")


if __name__ == "__main__":
    main()
