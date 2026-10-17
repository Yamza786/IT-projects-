import pytest
from ticket_service import create_ticket,response_target_hours

@pytest.mark.parametrize("priority,hours",[("urgent",1),("high",4),("normal",24),("low",72)])
def test_response_targets(priority,hours):assert response_target_hours(priority)==hours

def test_ticket_trims_title():assert create_ticket("  Printer offline ","normal").title=="Printer offline"

@pytest.mark.parametrize("title",["", "  ","ab","x"*161])
def test_invalid_title_rejected(title):
    with pytest.raises(ValueError):create_ticket(title,"normal")

def test_unknown_priority_rejected():
    with pytest.raises(ValueError):create_ticket("Valid title","emergency")
