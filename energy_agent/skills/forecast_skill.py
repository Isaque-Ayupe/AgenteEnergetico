"""
Skill de previsão de consumo energético.

Realiza previsão da próxima hora de consumo com base no histórico das
últimas 24 horas, ajustes sazonais por temperatura externa e ajustes
por eventos no calendário acadêmico. Toda a lógica é em Python puro,
sem uso de LLM.
"""

from typing import List, Optional


def run_forecast(input_data: dict) -> dict:
    """
    Executa a previsão de consumo energético para a próxima hora.

    Calcula a média do histórico de consumo das últimas 24 horas e aplica
    ajustes baseados em temperatura externa e eventos do calendário.

    Ajustes aplicados:
        - Sazonal: ±0.05 kWh por grau acima de 25°C na temperatura externa.
        - Calendário: 'recess' ou 'holiday' reduz em 40%; 'exam' aumenta em 15%.
        - Risco de pico: sinalizado quando tariff_peak é True.

    Nível de confiança:
        - 'high': histórico com 20 ou mais registros.
        - 'medium': histórico com 10 ou mais registros.
        - 'low': histórico com menos de 10 registros.

    Args:
        input_data: Dicionário com os dados validados de entrada do ambiente.
                    Campos utilizados: energy_kwh_last_24h, external_temp_celsius,
                    calendar_event, tariff_peak.

    Returns:
        Dicionário com as chaves:
            - predicted_kwh_next_hour (float): Previsão de consumo em kWh.
            - confidence (str): Nível de confiança da previsão.
            - peak_risk (bool): Indicador de risco de horário de pico.
            - baseline_avg_kwh (float): Média base do consumo histórico.
    """
    try:
        # --- Extrair dados de entrada com tratamento de ausência ---
        history: List[float] = input_data.get("energy_kwh_last_24h", [])
        if not isinstance(history, list) or len(history) == 0:
            history = [0.0]

        external_temp: float = float(input_data.get("external_temp_celsius", 25.0))
        calendar_event: Optional[str] = input_data.get("calendar_event")
        tariff_peak: bool = bool(input_data.get("tariff_peak", False))

        # --- Calcular média base do histórico ---
        baseline_avg_kwh: float = sum(history) / len(history)
        predicted_kwh: float = baseline_avg_kwh

        # --- Ajuste sazonal por temperatura ---
        # Acima de 25°C: +0.05 kWh por grau excedente
        # Abaixo de 25°C: -0.05 kWh por grau abaixo (ajuste simétrico)
        if external_temp > 25.0:
            delta_temp: float = external_temp - 25.0
            predicted_kwh += delta_temp * 0.05

        # --- Ajuste por evento do calendário ---
        if calendar_event is not None:
            event_lower: str = calendar_event.strip().lower()
            if event_lower in ("recess", "holiday"):
                predicted_kwh *= 0.60  # Redução de 40%
            elif event_lower == "exam":
                predicted_kwh *= 1.15  # Aumento de 15%

        # --- Risco de pico tarifário ---
        peak_risk: bool = tariff_peak

        # --- Nível de confiança baseado no tamanho do histórico ---
        history_len: int = len(history)
        if history_len >= 20:
            confidence: str = "high"
        elif history_len >= 10:
            confidence = "medium"
        else:
            confidence = "low"

        # --- Garantir valor não negativo ---
        predicted_kwh = max(predicted_kwh, 0.0)

        return {
            "predicted_kwh_next_hour": round(predicted_kwh, 4),
            "confidence": confidence,
            "peak_risk": peak_risk,
            "baseline_avg_kwh": round(baseline_avg_kwh, 4),
        }

    except Exception as e:
        return {
            "predicted_kwh_next_hour": 0.0,
            "confidence": "low",
            "peak_risk": False,
            "baseline_avg_kwh": 0.0,
            "error": f"Erro na previsão de consumo: {str(e)}",
        }
