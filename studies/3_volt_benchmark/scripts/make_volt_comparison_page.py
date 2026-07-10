"""Build the thesis Volt-comparison figures volt_compare_prices.png and
volt_compare_savings.png.

Earlier versions pasted a screenshot of Volt/BCG's own figure above our
reproduction.  The screenshots have been removed: the thesis now shows ONLY
the PowerGAMA reproduction in Volt's stacked-bar style, with Volt's published
values (report Figs. 1-2) overlaid as reference markers in the same axes.
That reproduction (and the overleaf copies) is produced by plot_volt_style.py,
which this script simply invokes so there is a single entry point.
"""
import runpy
import pathlib

_STYLE = pathlib.Path(__file__).resolve().parent / 'plot_volt_style.py'

if __name__ == '__main__':
    runpy.run_path(str(_STYLE), run_name='__main__')
