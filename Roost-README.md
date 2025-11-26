
# RoostGPT generated pytest code for API Testing

RoostGPT generats code in `tests` folder within given project path.
Dependency file i.e. `requirements-roost.txt` is also created in the given project path

Below are the sample steps to run the generated tests. Sample commands contains use of package manager i.e. `uv`. Alternatively python and pip can be used directly. 
1. ( Optional ) Create virtual Env .
2. Install dependencies
```
uv venv                                   // Create virtual Env
uv pip install -r requirements-roost.txt  // Install all dependencies

```

Test configurations and test_data is loaded from config.yml. e.g. API HOST, auth, common path parameters of endpoint. 
Either set defalt value in this config.yml file OR use ENV. e.g. export API_HOST="https://example.com/api/v2"

Once configuration values are set, use below commands to run the tests.
```
// Run generated tests
uv run pytest -m smoke                    // Run only smoke tests
uv run pytest -s tests/generated-test.py  // Run specific test file
```
 