"""Small pure functions used for testing practice."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Ticket:
    title: str
    priority: str

def create_ticket(title: str, priority: str) -> Ticket:
    title=title.strip()
    if not 3<=len(title)<=160: raise ValueError("title must be 3..160 characters")
    if priority not in {"low","normal","high","urgent"}: raise ValueError("unsupported priority")
    return Ticket(title,priority)

def response_target_hours(priority: str) -> int:
    targets={"urgent":1,"high":4,"normal":24,"low":72}
    try:return targets[priority]
    except KeyError:raise ValueError("unsupported priority") from None
