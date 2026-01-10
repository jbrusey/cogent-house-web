from enum import StrEnum

from cogent.base.model import LastReport


class LastReportName(StrEnum):
    FRIDGE_OVER_TEMP = "FridgeOverTemp"
    PANTRY_HUMIDITY_HIGH = "PantryHumidityHigh"


def get_last_report_flag(session, name: LastReportName):
    report = (
        session.query(LastReport).filter(LastReport.name == name.value).first()
    )
    active = report is not None and report.value == "True"
    return report, active


def set_last_report_flag(
    session, name: LastReportName, active: bool, report: LastReport | None = None
):
    if report is None:
        report = (
            session.query(LastReport)
            .filter(LastReport.name == name.value)
            .first()
        )
    if report is None:
        report = LastReport(name=name.value, value=str(active))
        session.add(report)
    else:
        report.value = str(active)
    session.commit()
    return report
