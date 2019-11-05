from bs4 import BeautifulSoup
import requests
import time
from datetime import datetime

URL = 'https://phabricator.services.mozilla.com/feed/transactions/'
BASE_URL = "https://phabricator.services.mozilla.com"


class PhabEventListener:

    def __init__(self):
        self.running = True
        self.url = URL
        self.base_url = BASE_URL
        self.timer_in_seconds = 60
        self.queue = []
        self.latest = None
        self.blacklist = ['added inline comments.',
                          'added a comment.',
                          'marked an inline comment as done.',
                          'edited the summary of this revision.',
                          'added a reviewer:',
                          'added a subscriber:',
                          'added a project:']
        self.datetime_format = "%a, %b %d, %I:%M %p"

    def run(self):
        # Run until told to stop.
        while self.running:
            resp = requests.get(self.url,
                                headers={
                                    'User-Agent': 'WptSync Bot / dheiberg@mozilla.com'
                                })

            if resp.status_code >= 400:
                print("Error! Got response status %d. Response: %s" % (resp.status_code, resp.content))
                self.running = False
                continue

            self.parse(resp)
            print('Sleeping')
            time.sleep(self.timer_in_seconds)

    def parse(self, response):
        soup = BeautifulSoup(response.content, 'html.parser')

        table = soup.find('table', {"class": "aphront-table-view"})
        rows = table.find_all("tr")
        assert rows[0].th.text == "Author"

        # Check if the events on this page will catch us up to our current state
        last_cell = rows[-1].find_all("td")
        last_timestamp = datetime.strptime(last_cell[3].text, self.datetime_format)
        if self.latest is not None and last_timestamp >= self.latest['timestamp']:
            # TODO We may need to paginate
            print("Error, too far out of sync")
            raise SystemExit

        latest = self.latest
        caught_up = False

        # Go through rows in reverse order, and ignore first row as it has the table headers
        for row in rows[:0:-1]:
            cells = row.find_all("td")
            event = {
                "author": cells[0].a.text,
                "phab_object": cells[1].a['href'],
                "transaction": self.parse_transaction(cells[2].div.span),
                "timestamp": datetime.strptime(cells[3].text, self.datetime_format)
            }

            # Check if we have reached the point where we will find new events
            if latest is None or event == self.latest:
                caught_up = True
            elif not caught_up:
                continue

            # Check if this is an event we wish to ignore
            if len(event['transaction']) == 1 and event['transaction'][0] in self.blacklist:
                # print("Discarded: %s" % event)
                continue

            # Add the event to the queue, and set this as the latest parsed
            self.queue.append(event)
            latest = event
            print(event)

        # Update the latest to be the last event we parsed here
        self.latest = latest

    def parse_transaction(self, transaction):
        text = [s.strip() for s in transaction.children if isinstance(s, basestring) and s != '.']
        return text


if __name__ == "__main__":
    listener = PhabEventListener()
    listener.run()
