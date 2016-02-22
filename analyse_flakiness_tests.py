from collections import Counter
from pprint import pprint

import os
import json

import requests


USERNAME = os.environ.get('JENKINS_USERNAME')
PASSWORD = os.environ.get('JENKINS_PASSWORD')
URL = os.environ.get('JENKINS_URL', "http://jenkins.com/")
JOB_NAME = os.environ.get('JOB_NAME')
JENKINS_RESPONSE_TIMEOUT = 60


class JenkinsAPIException(Exception):
    """
    Base class for all errors
    """
    pass


class NotFound(JenkinsAPIException):

    """Resource cannot be found
    """
    pass


class JenkinsJob(object):
    def __init__(self, base_url,
                 username=None, password=None,
                 job_name=None, build_number=None,
                 suffix='api/json'):
        self._base_url = self.strip_trailing_slash(base_url)
        self._username = username
        self._password = password
        self._job_name = job_name
        self._build_number = build_number
        self._data = None
        self.suffix = suffix

    def get_data_from_api(self):
        url = self._json_api_url(self._base_url, suffix=self.suffix)
        params = {
            u'auth': (self._username, self._password),
            u'timeout': JENKINS_RESPONSE_TIMEOUT
        }

        response = requests.get(url, **params)
        print(url)
        if response.status_code != 200:
            raise NotFound('Status code %s' % response.status_code)
        try:
            self._data = response.json()
        except ValueError:
            raise JenkinsAPIException('Cannot parse %s' % response.content)

    @staticmethod
    def strip_trailing_slash(url):
        url_ = url
        while url_.endswith('/'):
            url_ = url_[:-1]
        return url_

    def _json_api_url(self, url, suffix=None):
        """
        :param url: Jenkins main url e.g. http://jenkins.test.com/
        :return: json api url e.g.
        http://jenkins.test.com/job/job_name/1/api/json
        """
        fmt = "{}/job/{}/{}/{}"
        return fmt.format(self._base_url, self._job_name,
                          self._build_number, suffix)

    def get_status(self):
        status = self._data["result"].lower()
        if status != 'success':
            status = 'failure'
        return status

    def get_url(self):
        return self._data['url']

    def get_build_data(self):
        self.get_data_from_api()
        data = {
            u'status': self.get_status(),
            u'build_url': self.get_url(),
        }
        data.update(self.get_extra_parameters())
        return data

    def get_extra_parameters(self):
        actions = self._data.get('actions', [])
        parameters = {}
        for action in actions:
            if 'parameters' in action.keys():
                parameters = action['parameters']
        extra_parameters = {}

        for parameter in parameters:
            param = self.parameter_to_dict(parameter)
            extra_parameters.update(param)
        return extra_parameters

    @staticmethod
    def parameter_to_dict(parameter):
        """
        Convert Jenkins params to dict
        :param parameter:
        :rtype: dict
        """
        parameter_dict = {}
        name = parameter.get('name')
        value = parameter.get('value')
        parameter_dict[name] = value
        return parameter_dict


def get_failed_and_master_builds(start_build_number=None,
                                 end_build_number=None,
                                 stats_file='stats'
                                 ):
    arr = []
    for x in range(start_build_number, end_build_number):
        print x
        job = JenkinsJob(URL, username=USERNAME, password=PASSWORD,
                         job_name=JOB_NAME, build_number=x, suffix='api/json')
        try:
            build_data = job.get_build_data()
            # pprint(build_data)
            if build_data['sha1'] == 'origin/master' and \
                            build_data['status'] != 'success':
                arr.append(x)
                with open(stats_file, 'a') as outfile:
                    outfile.write("%s\n" % x)
        except ValueError:
            pass
    print arr


def get_and_save_failed_tests(stats_file='stats',
                              xunit_log_dir='logs'):
    arr = []
    if not os.path.exists(xunit_log_dir):
        os.mkdir(xunit_log_dir)

    with open(stats_file, 'r') as file:
        out = file.readlines()
        arr = list(map(int, out))
    print arr
    for build_number in arr:
        import json
        file_name = '{}/jenkins_build_{}.json'.format(xunit_log_dir, build_number)
        if not os.path.exists(file_name):
            with open(file_name, 'w') as outfile:
                job = JenkinsJob(URL, username=USERNAME, password=PASSWORD,
                                 job_name=JOB_NAME, build_number=build_number,
                                 suffix=r"api/json")
                try:
                    json.dump(job._data, outfile)
                except ValueError:
                    pass


def parse():
    c = Counter()
    results = {}
    for file_name in os.listdir('logs'):
        print file_name
        build_number = int(file_name.split('_')[2].split('.')[0])
        data = None
        with open('logs/%s' % file_name, 'r') as f:
            try:
                data = json.load(f)
                cases = data['suites'][0]['cases']
                for tc in cases:
                    if tc.get('status') in (u'FAILED', u'REGRESSION'):
                        # pprint(tc)
                        uid = "%s:%s" % (tc.get('className'), tc.get('name'))
                        c[uid] += 1
                        if results.get(uid):
                            results[uid].append(build_number)
                        else:
                            results[uid] = [build_number]
            except ValueError:
                pass
    pprint(c)
    for el in c.most_common(10):
        print el
        print results.get(el[0])


if __name__ == '__main__':
    """
    Main logic
    1. Get list of ids builds that run job_name on master to file stats
    2. Save all xunit logs from stats file build ids
    3. Parse logs and get failed tests from logs folder
    """
    get_failed_and_master_builds(1, 2)
    get_and_save_failed_tests()
    parse()