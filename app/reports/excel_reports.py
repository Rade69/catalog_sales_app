from __future__ import annotations

from pathlib import Path

import pandas as pd


class ExcelReports:
    @staticmethod
    def export_dataframe(df: pd.DataFrame, output_path: str | Path) -> Path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_excel(output_path, index=False)
        return output_path
