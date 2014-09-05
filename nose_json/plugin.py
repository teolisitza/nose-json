"""
nose_json.plugin
~~~~~~~~~~~~~~~~

:copyright: 2012 DISQUS, 2014 Cumulus Networks, Inc
:license: BSD
"""
import codecs
import os
import simplejson
import traceback
import datetime
import re
from time import time
from nose.exc import SkipTest
from nose.plugins import Plugin
from nose.plugins.xunit import id_split, nice_classname, exc_message


class JsonReportPlugin(Plugin):
    name = 'json'
    score = 2000
    encoding = 'UTF-8'

    def _get_time_taken(self):
        if hasattr(self, '_timer'):
            taken = time() - self._timer
        else:
            # test died before it ran (probably error in setup())
            # or success/failure added before test started probably
            # due to custom TestResult munging
            taken = 0.0
        return taken

    def options(self, parser, env):
        Plugin.options(self, parser, env)
        parser.add_option(
            '--json-file', action='store',
            dest='json_file', metavar="FILE",
            default=env.get('NOSE_JSON_FILE', 'nosetests.json'),
            help=("Path to json file to store the report in. "
                  "Default is nosetests.json in the working directory "
                  "[NOSE_JSON_FILE]"))

    def configure(self, options, config):
        Plugin.configure(self, options, config)
        self.config = config
        if not self.enabled:
            return

        self.start_time = datetime.datetime.utcnow().isoformat()
        self.stats = {
            'errors': 0,
            'failures': 0,
            'passes': 0,
            'skipped': 0,
        }
        self.results = []

        report_output = options.json_file

        path = os.path.realpath(os.path.dirname(report_output))
        if not os.path.exists(path):
            os.makedirs(path)

        self.report_output = report_output

    def report(self, stream):
        self.end_time = datetime.datetime.utcnow().isoformat()
        self.stats['encoding'] = self.encoding
        self.stats['total'] = (self.stats['errors'] + self.stats['failures']
                               + self.stats['passes'] + self.stats['skipped'])

        with codecs.open(self.report_output, 'w', self.encoding, 'replace') as fp:
            fp.write(simplejson.dumps({
                'stats': self.stats,
                'start_time': self.start_time,
                'end_time': self.end_time,
                'results': self.results,
            }))

    def startTest(self, test):
        self._timer = time()

    def findDoc(self, test, name):
        curr_test_obj = test
        while hasattr(curr_test_obj, 'test'):
            curr_test_obj = curr_test_obj.test
        if hasattr(curr_test_obj, name):
            curr_test_obj = getattr(curr_test_obj, name)
        return curr_test_obj.__doc__

    def findTags(self, test, name):
        curr_test_obj = test
        while hasattr(curr_test_obj, 'test'):
            curr_test_obj = curr_test_obj.test
        if hasattr(curr_test_obj, 'tags'):
            return curr_test_obj.tags
        if hasattr(curr_test_obj, name):
            curr_test_obj = getattr(curr_test_obj, name)
            if hasattr(curr_test_obj, 'tags'):
                return curr_test_obj.tags

    def addError(self, test, err, capt=None):
        taken = self._get_time_taken()

        if issubclass(err[0], SkipTest):
            type = 'skipped'
            self.stats['skipped'] += 1
        else:
            type = 'error'
            self.stats['errors'] += 1
        tb = ''.join(traceback.format_exception(*err))
        test_id = test.id()
        name = id_split(test_id)[-1]
        output = self._scrap_data_(exc_message(err))
        self.results.append({
            'id': test_id,
            'name': name,
            'time': taken,
            'tags': self.findTags(test, name),
            'doc': self.findDoc(test, name),
            'type': type,
            'errtype': nice_classname(err[0]),
            'ts': datetime.datetime.utcnow().isoformat(),
            # Too much text gets put here, can make our documents too big.
            #'message': exc_message(err),
            #'tb': tb,
            'message' : output['summary'],
            'tb' : output['detail'],
        })

    def addFailure(self, test, err, capt=None, tb_info=None):
        taken = self._get_time_taken()
        tb = ''.join(traceback.format_exception(*err))
        self.stats['failures'] += 1
        test_id = test.id()
        name = id_split(test_id)[-1]
        output = self._scrap_data_(exc_message(err))
        self.results.append({
            'id': test_id,
            'name': name,
            'time': taken,
            'tags': self.findTags(test, name),
            'doc': self.findDoc(test, name),
            'type': 'failure',
            'errtype': nice_classname(err[0]),
            'ts': datetime.datetime.utcnow().isoformat(),
            # Too much text gets put here, can make our documents too big.
            #'message': exc_message(err),
            #'tb': tb,
            'message' : output['summary'],
            'tb' : output['detail'],
        })

    def addSuccess(self, test, capt=None):
        taken = self._get_time_taken()
        self.stats['passes'] += 1
        test_id = test.id()
        name = id_split(test_id)[-1]
        self.results.append({
            'id': test_id,
            'name': name,
            'time': taken,
            'tags': self.findTags(test, name),
            'doc': self.findDoc(test, name),
            'ts': datetime.datetime.utcnow().isoformat(),
            'type': 'success',
        })

    def _scrap_data_(self, buf):
        lines = buf.splitlines()
        top_info = False
        info = {'summary': [],
                'detail' : []}

        for ln in lines:
            if re.findall('\S+.* begin', ln):
                top_info = True

            # Capture the initial lines in the output till you see
            # "begin capture" in the line
            if not(top_info):
                info['summary'].append(ln)

            # Don't capture and information until we see the "Error" and then
            # capture all the traceback info until we see the node cleaning up
            # TODO: need to handle the case where we see a core or WARN/ERR/CRIT
            #       msg
            if (len(info['detail']) > 0) and not('tests.lib.decorators: INFO:' in ln):
                info['detail'].append(ln)
            elif (len(info['detail']) > 0) and ('tests.lib.decorators: INFO:' in ln):
                break

            if re.findall('tests.lib.decorators: ERROR:.*', ln) and \
               top_info:
                info['detail'].append(ln)

        # Return a string instead of a list of strings
        info['summary'] = "\n".join(info["summary"])
        info['detail'] = "\n".join(info["detail"])

        return info
