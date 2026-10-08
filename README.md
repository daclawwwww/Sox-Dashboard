# SOXX Momentum Dashboard

Run `pip install -r requirements.txt`, set the environment variable `FRED_API_KEY`, then `streamlit run App.py`.

The live score uses only date-validated technical and observed macro inputs. Missing coverage withholds recommendations. Semiconductor sales and named memory context are dated manual snapshots; see [METHODOLOGY.md](METHODOLOGY.md) for provenance, expiry, exclusions, weights and update procedures. Hypothetical scenarios are isolated from live scoring.

Run offline regression tests with `pip install pytest` and `python -m pytest -q`. Tests include a mocked Streamlit app run and require no live API keys. No trading-performance claim is made.
