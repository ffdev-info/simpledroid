# simpledroid

`simpledroid` provides a way to convert a complete set of PRONOM XML exports to
a a simplified DROID signature file. It is based on my work on
[wd-droidy][wddroidy-1].

[wddroidy-1]: https://exponentialdecay.co.uk/blog/making-droid-work-with-wikidata/

## Why?

Simply completing the circle on the simplified DROID work. The mechanism reduces
the barriers to entry for writing signature files for DROID opening up new
opportunities for testing and customization. It also makes future PRONOM
development effort easier by reducing the barriers needed to output a compatible
signature file.

## Reference file

There is a reference signature file in the [reference][ref-1] folder.

[ref-1]: https://github.com/ross-spencer/simpledroid/tree/main/reference

## Building your own

### Download a PRONOM export

You need PRONOM's XML reports to build your own signature file. The best way
to access this information is from Richard Lehane's [builder][builder-1]. Its
zipped releases containing versioned reports, and their matching skeleton files
for testing.

[builder-1]: https://github.com/richardlehane/builder/releases/tag/v119a

### Run the simpledroid.py script

Usage is described as follows:

```text
usage: simpledroid [-h] [--pronom PRONOM] [--output OUTPUT] [--output-date]

create a complete simplified DROID signature file from a PRONOM export

options:
  -h, --help            show this help message and exit
  --pronom PRONOM, -p PRONOM
                        point to a set of droid reports, e.g. from builder
  --output OUTPUT, -o OUTPUT
                        filename to output to
  --output-date, -t     output a default file with the current timestamp

for more information visit https://github.com/ffdev-info/simpledroid
```

The default distribution contains a PRONOM export. This can be overridden
using the `--pronom` flag, e.g.

```sh
python simpledroid.py --pronom /path/to/pronom-export/
```

## More information

More information will appear here in the fullness of time. Take a look at
wd-droidy for more info and let me know if you make use of any of this work.

## License

Apache License v2.0.
