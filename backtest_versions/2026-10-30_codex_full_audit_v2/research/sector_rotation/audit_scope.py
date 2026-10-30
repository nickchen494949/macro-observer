"""Explicit labels for inherited retrospective sector research."""
import sys

def require_revised_history():
    if '--revised-history' not in sys.argv:
        raise SystemExit('BLOCK: PE/macro historical vintages unverified. '
                         'Use --revised-history for retrospective research only.')
    print('REVISED_HISTORY_ONLY; GROSS_UNLESS_MARKED; source vintages not certified; '
          'event/conditional statistics are not portfolio returns.')
