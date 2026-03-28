# Test Scripts

| Script | Command | Tests |
|--------|---------|-------|
| `test_login.py` | `python test_login.py` | Session check → login → OTP (if needed) |
| `test_profile.py` | `python test_profile.py` | Resume upload + AI headline + AI summary saved to Naukri |
| `test_apply.py` | `python test_apply.py` | Full pipeline: scrape → filter → LLM score → apply (2 jobs, no delays) |

## Notes

- Run them in order — login first, then profile, then apply.
- `test_apply.py` submits **real applications**. It uses `TEST_MODE=True` (2 jobs, all delays stripped).
- To go production, set `TEST_MODE = False` in `services/jobs/job_session.py` and run the scheduler:
  ```
  python -m services.scheduler.scheduler_service
  ```
