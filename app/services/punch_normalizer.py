from dataclasses import dataclass


@dataclass
class NormalizedPunch:
    biotime_id: int
    emp_code: str
    punch_time: str
    punch_state: str
    terminal_sn: str | None
    terminal_alias: str | None
    raw_payload: dict

    @property
    def is_check_in(self) -> bool:
        # punch_state=0 → Check In  (confirm with client before go-live)
        return self.punch_state == "0"

    @property
    def is_check_out(self) -> bool:
        # punch_state=1 → Check Out (confirm with client before go-live)
        return self.punch_state == "1"


class PunchNormalizer:
    def normalize(self, raw: dict) -> NormalizedPunch:
        for field in ("id", "emp_code", "punch_time"):
            if field not in raw:
                raise ValueError(f"BioTime transaction missing field '{field}': {raw}")

        return NormalizedPunch(
            biotime_id=int(raw["id"]),
            emp_code=str(raw["emp_code"]),
            punch_time=str(raw["punch_time"]),
            punch_state=str(raw.get("punch_state", "")),
            terminal_sn=raw.get("terminal_sn"),
            terminal_alias=raw.get("terminal_alias"),
            raw_payload=raw,
        )
