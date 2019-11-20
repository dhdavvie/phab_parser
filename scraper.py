import time
import re
from phabricator import Phabricator
import os

URL = "https://phabricator.services.mozilla.com/feed/transactions/"
BASE_URL = "https://phabricator.services.mozilla.com"


def map_feed_tuple(feed_tuple):
    story_phid, feed_story = feed_tuple
    feed_story.update({"storyPHID": story_phid})
    return feed_story


class PhabEventListener:

    def __init__(self, config):
        self.running = True
        self.url = URL
        self.base_url = BASE_URL
        self.timer_in_seconds = config['phabricator']['listener']['interval']
        self.queue = []
        self.latest = None
        self.blacklist = ["added inline comments to D",
                          "added a comment to D",
                          "added a reviewer for D",
                          "removed a reviewer for D",
                          "requested review of D",
                          "added a subscriber to D",
                          "added a project to D"]
        self.datetime_format = "%a, %b %d, %I:%M %p"

        self.phab = Phabricator(host='https://phabricator.services.mozilla.com/api/',
                            token=config['phabricator']['token'])
        self.phab.update_interfaces()

    def run(self):
        # Run until told to stop.
        while self.running:
            feed = self.get_feed()
            print("Got feed: %s" % feed)
            self.parse(feed)
            time.sleep(self.timer_in_seconds)

    def get_feed(self, before=None):
        """ """
        if self.latest and before is None:
            before = int(self.latest['chronologicalKey'])

        done = False
        feed = []

        def chrono_key(feed_story_tuple):
            return int(feed_story_tuple[1]["chronologicalKey"])

        # keep fetching stories from Phabricator until there are no more stories to fetch
        while not done:
            result = self.phab.feed.query(before=before, view='text')
            if result.response:
                print("Response: %s" % result.response)
                results = sorted(result.response.items(), key=chrono_key)
                results = map(map_feed_tuple, results)
                feed.extend(results)
                if len(results) == 100 and before is not None:
                    # There may be more events we wish to fetch
                    before = int(results[-1]["chronologicalKey"])
                    done = False
                    continue
            done = True
        return feed

    def parse(self, feed):
        latest = self.latest
        caught_up = False

        # Go through rows in reverse order, and ignore first row as it has the table headers
        for event in feed:

            # Split the text to get the part that describes the event type
            event_text = re.compile("[0-9]{5}:").split(event['text'])[0]

            # Check if this is an event we wish to ignore
            if any([event_type in event_text for event_type in self.blacklist]):
                continue

            # Add the event to the queue, and set this as the latest parsed
            self.queue.append(event)
            self.latest = event
            print("Event", event['text'])

        # Update the latest to be the last event we parsed here
        self.latest = latest


def run_phabricator_listener(config):
    listener = PhabEventListener(config)
    listener.run()


if __name__ == "__main__":
    config = {
        'phabricator': {
            'listener': {
                'interval': 60
            },
            'token': os.getenv('PHAB_TOKEN', None)
        }
    }

    run_phabricator_listener(config)