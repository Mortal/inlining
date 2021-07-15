#!/bin/bash
python3 inlining.py --input /usr/lib/python3.9/base64.py --location 'b64encode(s).translate' | wc
python3 inlining.py --input /usr/lib/python3.9/base64.py --location '_85encode(b, _a85chars' | wc
python3 inlining.py --input /usr/lib/python3.9/base64.py --location 'encodebytes(s0)' | wc
python3 inlining.py --input /usr/lib/python3.9/binhex.py --location 'getfileinfo(inp)' | wc
python3 inlining.py --input /usr/lib/python3.9/bisect.py --location 'bisect_right(a, x, lo, hi)' | wc
python3 inlining.py --input /usr/lib/python3.9/bisect.py --location 'bisect_left(a, x, lo, hi)' | wc
python3 inlining.py --input /usr/lib/python3.9/calendar.py --location 'formatstring(weeks, colwidth, c)' | wc
python3 inlining.py --input /usr/lib/python3.9/cgitb.py --location 'lookup(token, frame, locals)' | wc
python3 inlining.py --input /usr/lib/python3.9/codecs.py --location 'getincrementaldecoder(encoding)(errors, **kwargs)' | wc
