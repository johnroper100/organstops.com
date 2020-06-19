import json
import logging
import os
import re
import string
from collections import namedtuple
from pathlib import PurePath

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag


LOGGER = logging.getLogger(__name__)

BIBLIOGRAPHY = 'Bibliography'
EXAMPLES = 'Examples'
FOOTER = 'Footer'
IGNORE = 'IGNORE'
NAMES = 'NAMES'
NOT_DONE = 'NotDone'
PRIMARY = 'PRIMARY'
SPONSOR_IMG_CLASS = 'Sponsor'
TONAL_ATTRIBUTES = 'Tonal Attributes'
UNKNOWN_ORIGIN = 'Unknown'
VARIANTS = 'Variants'

ExampleData = namedtuple('ExampleData', 'description examples')
StopName = namedtuple('StopName', 'name origin link primary')
Summary = namedtuple('Summary', 'description construction usage')

# Still to-do:
#     - comparisons
#     - Bibliography

# Files that don't work with the converter for various reasons
# We'll need to do these by hand or edit the converter to handle their cases
# and rerun just for them
SKIP = (
    'CelloCeleste',  # annoying text with link in examples
    'Gemshorn',  # missing closing <tr/> in sound clips
    'LieblichGedeckt',  # missing closing <tr/> in sound clips
    'OrchFlute',  # encoding issues
    'Ottavino',  # encoding issues
    'Flute',  # uses external table for variants
    'Resultant',  # has a mini-essay for variants
    'Rohrgedeckt',  # has direct links for variants
)

# Characters that start files we shouldn't parse
HIDDEN_LEADERS = ('_', '.')


def get_next_comment(element):
    maybe_comment = element.next_sibling
    while isinstance(maybe_comment, NavigableString):
        if isinstance(maybe_comment, Comment):
            return maybe_comment

        maybe_comment = maybe_comment.next_sibling

    return None


def get_previous_comment(element):
    maybe_comment = element.previous_sibling
    while isinstance(maybe_comment, NavigableString):
        if isinstance(maybe_comment, Comment):
            return maybe_comment

        maybe_comment = maybe_comment.previous_sibling

    return None


def extract_path_from_descendant_link(element, interested_in=1, require=True):
    path = None
    for desc in element.descendants:
        if desc.name != 'a':
            continue
        path = desc['href'].rsplit('/', interested_in)[-interested_in]
        break

    if require:
        assert path, f"could not find sub-link in {element}"

    return path


def extract_sound_clips(soup):
    samples_table = soup.find('table', {'class': 'samples'})

    if not samples_table:
        return []

    def init_division(name=""):
        return {'divisionName': name, 'clips': []}

    current_division = init_division()
    clips = []

    for row in samples_table.find_all('tr'):
        clip = {'files': []}
        if 'samples' in row.get('class', []):
            for col_ix, col in enumerate(row.find_all('td')):
                if col_ix == 0:
                    clip['name'] = finalize(col.text)

                elif col_ix == 1:
                    link = extract_path_from_descendant_link(
                        col, interested_in=2, require=False)

                    if link:
                        clip['organLink'] = link
                    else:
                        clip['organLink'] = ""

                    clip['organName'] = finalize(col.text)

                elif col_ix == 2:
                    clip['organBuilderName'] = finalize(col.text)

                elif col_ix >= 3:
                    if col.text.strip():
                        text = col.text.lower().replace('\xa0', ' ')

                        # Explicitly handle all of the cases so we know we get
                        # sensible names in the output
                        if text == 'arpeggio':
                            name = 'Arpeggio'

                        elif text == "arpeggio (16')":
                            name = "Arpeggio (16')"

                        elif text == "arpeggio (trem.)":
                            name = "Arpeggio (trem.)"

                        elif text == 'bottom 15 notes':
                            name = 'Bottom 15 notes'

                        elif text == 'st. anne':
                            name = 'St. Anne'

                        elif text == 'st. anne (8va)':
                            name = 'St. Anne (8va)'

                        elif text == 'st. anne (solo)':
                            name = 'St. Anne (Solo)'

                        elif text == 'st. anne (trem.)' or \
                                text == 'st. anne (tremolo)':
                            name = 'St. Anne (Trem.)'

                        elif text == '1 & 2' or text == '1 then 2 then both':
                            name = text

                        elif 'see' in text:
                            continue

                        else:
                            raise RuntimeError(
                                f'unknown clip name: {col.text}')

                        path = extract_path_from_descendant_link(col)
                        clip['files'].append({
                            'name': name,
                            'file': path,
                        })

            current_division['clips'].append(clip)

        else:
            division = row.text.split()[0]
            assert division in ('Manual', 'Pedal')
            if current_division['clips']:
                clips.append(current_division)

            current_division = init_division(division)

    if current_division['clips']:
        clips.append(current_division)
    return clips


def extract_example_data(soup):
    for h2 in soup.find_all('h2'):
        if h2.text == EXAMPLES:
            description = get_next_element(h2)
            if description.name == 'p':
                description_text = finalize(description.text)

            elif isinstance(description, NavigableString):
                description_text = finalize(description)

            else:
                # TODO: check these cases more carefully
                return ExampleData("", [])

            raw_examples = soup.findAll('p', {'class': 'example'})
            examples = list(map(lambda ex: {
                'link': '',
                'name': finalize(ex.text)
            }, raw_examples))

            # Sometimes, the last example is missing a closing </p>
            # If it is, then we discard that example
            # to avoid returning the entire end of the page as well.
            if examples and BIBLIOGRAPHY in examples[-1]['name']:
                examples = examples[:-1]

            return ExampleData(description_text, examples)

    # There are some cases without an example block (e.g., Botze)
    return ExampleData("", [])


def get_next_element(element):
    current = element.next_sibling
    while isinstance(current, NavigableString) and current == "\n":
        current = current.next_sibling

    return current


def extract_bibliography(soup):
    # TODO
    return []


def extract_images(soup):
    images = []
    for img in soup.find_all("img"):
        if SPONSOR_IMG_CLASS not in img.get("class", []):
            images.append({
                "file": img.get("src"),
                "subtitle": "",
            })

    return images


def extract_variants(soup):
    variants = []
    for h2 in soup.find_all('h2'):
        if h2.text == VARIANTS:
            variants_element = get_next_element(h2)
            if variants_element.name == 'table':
                for desc in variants_element.descendants:
                    if desc.name == 'a':
                        path = desc['href'].rsplit('/', 1).pop()
                        variants.append({
                            "name": finalize(desc.text),
                            "link": os.path.splitext(path)[0]
                        })
            elif variants_element.name == 'a':
                path = variants_element['href'].rsplit('/', 1).pop()
                variants.append({
                    "name": finalize(variants_element.text),
                    "link": os.path.splitext(path)[0]
                })

            elif variants_element.name == 'p':
                # For example, the Celeste page contains a note saying
                # "All of the celeste stops [...] are listed below"
                variants_element = get_next_element(variants_element)

            else:
                raise RuntimeError(
                    f'unknown variants element: {variants_element.name}')

    return variants


def extract_comparisons(soup):
    # TODO
    # Make exceptions for "See" in these lines:
    # - The practice is not unknown abroad
    # - See photos
    # - See the Sound Files appendix
    # - See also Credits
    # - See for examples of that name
    # - See below for sound clips
    # - See composition above
    # - See above

    # Look for links that match these criteria:
    #   - See <link>(, <link>, ...).
    #   - See also <link>(, <link>, ...).
    #   - Compare with <link>(, <link>, ...).
    return []


def finalize(string):
    return ' '.join(string.split()).strip()


def extract_summary_text(table):
    # The description usually begins immediately after the stop names table
    element = table.find_next_sibling('p')

    # Loop through elements until we find the actual description
    while True:
        if not element:
            return Summary("", "", "")

        # Skip the notes about the entry being under construction
        if NOT_DONE in element.get('class', []):
            element = element.find_next_sibling('p')
            continue

        # If there's an img tag here, it will actually be closed,
        # so arbitrarily skip over anything with only a few elements.
        if 'img' in [desc.name for desc in list(element.descendants)[:5]]:
            if len(list(element.descendants)) < 10:
                element = element.find_next_sibling('p')
                continue

        break

    # This paragraph node will not have a closing tag,
    # so read until we hit another section.

    summaries = {
        'description': "",
        'usage': "",
        'construction': "",
    }

    text = element.find_all(text=True)
    while get_next_element(element) and \
            get_next_element(element).name in ('p', 'blockquote'):
        element = get_next_element(element)
        if "FOOTER" in element:
            break
        text += element.find_all(text=True)

    current = 'description'

    for entry in text:
        if FOOTER in entry:
            break

        # Save the comparison lists for the comparisons section
        if entry.strip().startswith("See") or \
                entry.strip().startswith("Compare with"):
            break

        if entry == VARIANTS:
            break

        elif entry in ("Construction", "Usage"):
            current = entry.lower()
            continue

        # "Tonal Attributes" doesn't have a JSON section,
        # but shows up in a few entries. It should go in description.
        elif entry == TONAL_ATTRIBUTES:
            current = 'description'
            continue

        else:
            summaries[current] += entry.replace('\n', ' ')

    return Summary(*map(
        finalize, (summaries['description'],
                   summaries['construction'],
                   summaries['usage'])))


def extract_stop_names(table):
    names = []
    # Because of the way the HTML is structured, the two text nodes
    # (for name and origin) are always next to the br tag.
    for br in table.find_all('br'):
        if get_next_comment(br) == IGNORE:
            continue

        origin = br.previous_sibling
        name = ""

        if not isinstance(origin, NavigableString):
            stop_name = origin
            origin = UNKNOWN_ORIGIN

        else:
            stop_name = origin.previous_sibling

        descendants = list(stop_name.descendants)

        for tag in reversed(descendants):
            if isinstance(tag, NavigableString):
                name = tag + name
            else:
                break

        link = ""
        for child in descendants:
            if isinstance(child, Tag) and child.name == 'a':
                link = child['href']
                if '../' in link:
                    link = link.rsplit('/', 1)[-1]

        assert name.strip()
        if not origin.strip():
            origin = UNKNOWN_ORIGIN

        origin = origin.strip()
        if origin == "(unknown)":
            origin = UNKNOWN_ORIGIN

        primary = (get_next_comment(br) == PRIMARY)
        name_text = name.strip()
        if name_text.startswith("'"):
            name_text = name_text[1:].strip()

        names.append(StopName(name_text, origin, link, primary))

    return names


def collect_names_with_ext(base_dir, extension):
    names = set()
    for root, sub_dirs, _ in os.walk(base_dir):
        for sub_dir in sub_dirs:
            if sub_dir in string.ascii_lowercase:
                stops = os.listdir(os.path.join(root, sub_dir))
                for stop in stops:
                    if stop[0] in HIDDEN_LEADERS:
                        continue

                    file_name, ext = os.path.splitext(stop)
                    if ext == extension and file_name not in SKIP:
                        names.add(file_name)

    return names


def collect_old_stops(old_dir):
    old_names = collect_names_with_ext(old_dir, '.html')
    camel_to_snake = re.compile(r'(?<!^)(?=[A-Z])')
    new_names = set()
    for name in old_names:
        if '_' in name:
            new_names.add(name)
        else:
            new_names.add(camel_to_snake.sub('_', name))

    return new_names


def collect_converted_stops(new_dir):
    return collect_names_with_ext(new_dir, '.json')


def parse_old_file(old_path):
    LOGGER.debug(f"Will read data from {old_path}")
    with open(old_path, 'r') as data:
        soup = BeautifulSoup(data.read(), 'html.parser')

    converted = {
        "images": [],
    }

    # Find the table with alternate names
    for table in soup.find_all('table'):
        if get_previous_comment(table) == NAMES:
            names = extract_stop_names(table)
            assert names
            LOGGER.debug(f"found {len(names)} names")

            converted["names"] = [{
                "name": name.name,
                "origin": name.origin,
                "link": name.link,
                "primary": name.primary
            } for name in names]

            summary = extract_summary_text(table)

            converted["description"] = summary.description
            converted["construction"] = summary.construction
            converted["usage"] = summary.usage

    converted['images'] = extract_images(soup)

    LOGGER.debug(f"found {len(converted['images'])} images")

    converted["variants"] = extract_variants(soup)
    LOGGER.debug(f"found {len(converted['variants'])} variants")

    converted["comparisons"] = extract_comparisons(soup)

    example_data = extract_example_data(soup)
    converted["examplesDescription"] = example_data.description
    if example_data.description:
        LOGGER.debug("found example description text")

    else:
        LOGGER.debug("didn't find description text")

    example_data = extract_example_data(soup)
    converted["examples"] = example_data.examples
    if example_data.examples:
        LOGGER.debug(f"found {len(example_data.examples)} examples")

    else:
        LOGGER.debug("didn't find examples")

    sound_clips = extract_sound_clips(soup)
    converted["soundClips"] = sound_clips

    for division in sound_clips:
        LOGGER.debug(f"found {len(division['clips'])} sound clips "
                     f"for division {division['divisionName']}")

    converted["bibliography"] = extract_bibliography(soup)

    LOGGER.debug(f"Finished reading data from {old_path}")
    return converted


def write_new_file(data, new_file, dry_run):
    if dry_run:
        LOGGER.debug(f"Would write new file at {new_file}")

    else:
        if not os.path.exists(PurePath(new_file).parent):
            os.mkdir(PurePath(new_file).parent)

        with open(new_file, 'w') as output:
            json.dump(data, output)

        LOGGER.debug(f"Wrote new file at {new_file}")


def convert(stop, old_dir, new_dir, dry_run):
    old_name = f"{''.join(stop.split('_'))}.html"

    if os.path.exists(os.path.join(old_dir, old_name[0].lower(), old_name)):
        old_path = os.path.join(old_dir, old_name[0].lower(), old_name)
    else:
        old_path = os.path.join(old_dir, old_name[0].lower(), f"{stop}.html")

    new_path = os.path.join(new_dir, old_name[0].lower(), f"{stop}.json")
    LOGGER.debug(f"will convert {old_name} from {old_path} to {new_path}")

    stop_data = parse_old_file(old_path)
    write_new_file(stop_data, new_path, dry_run)


def main(old_dir, new_dir, rewrite, dry_run):
    stops = collect_old_stops(old_dir)
    LOGGER.debug(f"Found {len(stops)} old stops")

    if rewrite:
        LOGGER.debug("--rewrite passed, will rewrite all files")
        to_convert = stops

    else:
        converted = collect_converted_stops(new_dir)
        to_convert = stops - converted
        LOGGER.debug(f"Need to convert {len(to_convert)} stops")

    for stop in sorted(list(to_convert)):
        convert(stop, old_dir, new_dir, dry_run)

    # These files cover lots of edge cases that came up
    # It's a good idea to uncomment them and check the output manually
    # convert("Baarpijp", old_dir, new_dir)
    # convert("percussion", old_dir, new_dir)
    # convert("Aeolina", old_dir, new_dir)
    # convert("Open_Diapason", old_dir, new_dir)
    # convert("Aeoline", old_dir, new_dir)
    # convert("Trumpet", old_dir, new_dir)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("-o", "--old-directory", type=str, required=True,
                        help="Path to the directory with the old definitions")
    parser.add_argument("-n", "--new-directory", type=str, required=True,
                        help="Path to the directory with the new definitions")
    parser.add_argument("-r", "--rewrite", action='store_true',
                        help="If given, rewrite existing files")
    parser.add_argument("-d", "--dry-run", action='store_true',
                        help="If given, don't actually write files")
    args = parser.parse_args()

    if not os.path.exists(args.old_directory):
        raise RuntimeError(f"Path {args.old_directory} does not exist")

    if not os.path.exists(args.new_directory):
        os.makedirs(args.new_directory)

    main(args.old_directory, args.new_directory, args.rewrite, args.dry_run)
