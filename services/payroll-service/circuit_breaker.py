import pybreaker
import httpx
import os

EMPLOYEE_SERVICE_URL = os.getenv("EMPLOYEE_SERVICE_URL", "http://localhost:8001")

# Circuit breaker: opens after 5 failures, resets after 30 seconds
employee_breaker = pybreaker.CircuitBreaker(
    fail_max=5,
    reset_timeout=30,
    name="employee-service-breaker"
)

SALARY_GRADES = {
    "L1": 30000.0,
    "L2": 50000.0,
    "L3": 80000.0,
    "L4": 120000.0,
    "L5": 180000.0,
}

@employee_breaker
def fetch_employee(employee_id: str) -> dict:
    resp = httpx.get(f"{EMPLOYEE_SERVICE_URL}/employees/{employee_id}", timeout=5.0)
    resp.raise_for_status()
    return resp.json()

def get_employee_safe(employee_id: str) -> dict:
    """
    Returns employee data or a fallback if the circuit is open.
    Fallback uses L2 salary grade so payroll can still be processed.
    """
    try:
        return fetch_employee(employee_id)
    except pybreaker.CircuitBreakerError:
        print(f"[CircuitBreaker] OPEN — Employee service unreachable. Using fallback for {employee_id}")
        return {
            "id": employee_id,
            "salary_grade": "L2",
            "name": "Unknown (fallback)",
            "_fallback": True
        }
    except Exception as e:
        print(f"[CircuitBreaker] Error fetching employee {employee_id}: {e}")
        raise
