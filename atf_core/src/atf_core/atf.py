#!/usr/bin/env python
import rospy
import atf_core

from atf_msgs.msg import MetricResult, TestblockResult, TestblockTrigger
from smach_msgs.msg import SmachContainerStatus

###########
### ATF ###
###########
class ATF():
    def __init__(self):
        # get test config
        package_name = rospy.get_param("/atf/package_name")
        print "package_name:", package_name
        test_name = rospy.get_param("/atf/test_name")
        print "test_name:", test_name

        atf_configuration_parser = atf_core.ATFConfigurationParser(package_name)
        tests = atf_configuration_parser.get_tests()
        for test in tests:
            #print "test.name:", test.name
            if test_name == test.name:
                break
        #print "current test:", test.name
        self.test = test

        self.publisher_trigger = rospy.Publisher("atf/trigger", TestblockTrigger, queue_size=10)
        self.publisher_user_result = rospy.Publisher("atf/user_result", TestblockResult, queue_size=10)
        rospy.Subscriber("/state_machine/machine/smach/container_status", SmachContainerStatus, self._sm_status_cb)

        # make sure to wait with the application for the statemachine in sm_test.py to be initialized
        rospy.loginfo("waiting for smach container in test_sm to be ready...")
        rospy.wait_for_message("/state_machine/machine/smach/container_status", rospy.AnyMsg)
        #rospy.sleep(3) # FIXME remove
        rospy.loginfo("...smach container in sm_test is ready.")
    
    def start(self, testblock):
        if testblock not in self.test.test_config.keys():
            error_msg = "testblock %s not in list of testblocks"%testblock
            self._send_error(error_msg)
            raise atf_core.ATFError(error_msg)
        rospy.loginfo("starting testblock %s"%testblock)
        trigger = TestblockTrigger()
        trigger.stamp = rospy.Time.now()
        trigger.name = testblock
        trigger.trigger = TestblockTrigger.START
        self.publisher_trigger.publish(trigger)

    def stop(self, testblock):
        if testblock not in self.test.test_config.keys():
            error_msg = "testblock %s not in list of testblocks"%testblock
            self._send_error(error_msg)
            raise atf_core.ATFError(error_msg)
        rospy.loginfo("stopping testblock %s"%testblock)
        trigger = TestblockTrigger()
        trigger.stamp = rospy.Time.now()
        trigger.name = testblock
        trigger.trigger = TestblockTrigger.STOP
        self.publisher_trigger.publish(trigger)

    def shutdown(self):
        rospy.logdebug("shutting down atf application")

        # check if any testblock is still running
        rospy.logdebug("waiting for all states to be in a terminal state")
        r = rospy.Rate(10)
        while not rospy.is_shutdown():
            if self.sm_container_status.path == "SM_ATF/CON":
                if len(self.sm_container_status.active_states) == 0:
                    rospy.logdebug("all testblocks finished in SM_ATF/CON")
                    break
                rospy.logdebug("still waiting for active states in path 'SM_ATF/CON' to be prepempted. active_states: %s", str(self.sm_container_status.active_states))
                r.sleep()
                continue
        rospy.sleep(3) # FIXME we need to wait until sm_test.py is shutdown properly so that bag file can be closed by recorder.py in on_shutdown
        rospy.logdebug("atf application is shutdown.")

    def set_user_result(self, testblock, data, details):
        if not isinstance(data, float) and not isinstance(data, int):
            error_msg = "user_result.data is not a float or int. data=%s, type=%s"%(str(data), type(data))
            self._send_error(error_msg)
            raise atf_core.ATFError(error_msg)
        if type(details) is not list:
            error_msg = "user_result.details is not a list. detail=%s"%str(details)
            self._send_error(error_msg)
            raise atf_core.ATFError(error_msg)
        metric_result = MetricResult()
        metric_result.data = data
        metric_result.details = details
        testblock_result = TestblockResult()
        testblock_result.name = testblock
        testblock_result.results.append(metric_result)
        self.publisher_user_result.publish(testblock_result)

    def _send_error(self, error_msg):
        trigger = TestblockTrigger()
        trigger.stamp = rospy.Time.now()
        trigger.name = error_msg
        trigger.trigger = TestblockTrigger.ERROR
        self.publisher_trigger.publish(trigger)

    def _sm_status_cb(self, msg):
        self.sm_container_status = msg
