"""Helper script to set up symlink and launch IC simulations."""
import os
import subprocess
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
base = os.path.dirname(os.path.dirname(script_dir))  # project root
target = os.path.join(base, 'scenarios', 'baseline', 'data', 'timeseries_profiles.csv')
link = os.path.join(base, 'scenarios', 'nuclear_IC', 'data', 'timeseries_profiles.csv')

# Create symlink if needed
if not os.path.exists(link):
    os.symlink(target, link)
    print(f'Created symlink: {link} -> {target}')
else:
    print(f'Symlink already exists: {link}')

# Make shell script executable
sh_script = os.path.join(script_dir, 'run_all_IC.sh')
os.chmod(sh_script, 0o755)
print(f'Made executable: {sh_script}')

# Launch simulations
print('Starting IC simulations...')
run_script = os.path.join(script_dir, 'run_nuclear_IC.py')
logfile = os.path.join(script_dir, 'run_all_IC.log')

# Run all 4 scenarios sequentially
scenarios = sys.argv[1:] if len(sys.argv) > 1 else ['BL_IC', 'SMR1_IC', 'SMR3_IC', 'SMR6_IC']
with open(logfile, 'w') as log:
    for scenario in scenarios:
        print(f'Running {scenario}...')
        result = subprocess.run(
            [sys.executable, run_script, scenario],
            stdout=log, stderr=subprocess.STDOUT,
            cwd=base
        )
        if result.returncode != 0:
            print(f'  {scenario} failed with return code {result.returncode}')
        else:
            print(f'  {scenario} completed successfully')

print(f'\nAll done. Log: {logfile}')
