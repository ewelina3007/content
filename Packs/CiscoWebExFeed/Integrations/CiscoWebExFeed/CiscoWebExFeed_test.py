DOMAIN_TABLE = [['Client Type', 'Domain(s)'],
                ['domain1', '*.d1.com'],
                ['domain2', '*.d2.com'],
                ['Long message without domain name']]

IP_TABLE = [['Client Type', 'IP(s)'],
            ['\n\n\n0.0.0.0/0 (CIDR) or 1.1.1.1'],
            ['2.2.2.2 (net range)8.8.8.8/8 (CIDR)'],
            ['Long message without domain name']]


def test_grab_domains():
    """
    Given:
        - Raw list of tuples that contains domain name and domain url, returned by api call:
        first array is the title, 2 seconds arrays are data, last array is message.
    When:
        - Filtered list contains domain's urls only
    Then:
        - Return domains list without errors
    """
    from CiscoWebExFeed import grab_domains
    expected_result = ['*.d1.com', '*.d2.com']
    assert grab_domains(DOMAIN_TABLE) == expected_result


def test_grab_ips():
    """
    Given:
        -Raw list of lists that contains ips CIDR and net range, returned by api call:
        first array is the title, 2 seconds arrays are data, last array is message.
    When:
        - Filtered list contains domain's urls only
    Then:
        - Return CIDR ips list without errors
    """
    from CiscoWebExFeed import grab_ips
    expected_result = ['0.0.0.0/0', '8.8.8.8/8']
    assert grab_ips(IP_TABLE) == expected_result


html_section = '''<div class="panel-collapse collapse" id="id_135010">
<div class="panel-body">
<div class="body refbody">
<p class="li">Webex recommends that content should not be cached at any time. The following domain(s) will be used by meeting clients that connect to Webex Meetings:</p>
<table border="1" class="li" height="289" width="640"><tbody><tr><td colspan="1" rowspan="1"><b>Client Type</b></td><td colspan="1" rowspan="1"><b>Domain(s)  </b></td></tr><tr><td colspan="1" rowspan="1">Webex Meetings Desktop Application</td><td colspan="1" rowspan="1"><b>*.wbx2.com<br/>			*.ciscospark.com<br/>			*.webexcontent.com</b><br/>			 </td></tr><tr><td colspan="1" rowspan="1">Webex Desktop Clients (Mac/PC, including WebApp the browser based thin client) connecting to Webex Meetings</td><td colspan="1" rowspan="1"><b>*.webex.com</b></td></tr><tr><td colspan="1" rowspan="1">On-prem SIP/H323 devices calling into (or being called back from) a Webex Meeting</td><td colspan="1" rowspan="1"><b>*.webex.com</b> (note IP dialing also available)</td></tr><tr><td colspan="1" rowspan="1">Webex Mobile Clients (iOS, Android) connecting to Webex Meetings</td><td colspan="1" rowspan="1"><b>*.webex.com</b></td></tr><tr><td colspan="1" rowspan="1">Certificate Validation</td><td colspan="1" rowspan="1"><b>*.identrust.com<br/>			*.quovadisglobal.com<br/>			*.digicert.com<br/>			*.godaddy.com<br/>			*.lencr.org<br/>			*.intel.com</b></td></tr><tr><td colspan="1" rowspan="1">People Insights Integration</td><td colspan="1" rowspan="1"><b>*.accompany.com</b></td></tr><tr><td colspan="1" rowspan="1">Webex Meetings site performance analytics and Webex App</td><td colspan="1" rowspan="1">*.eum-appdynamics.com<br/>			*.appdynamics.com</td></tr><tr><td colspan="1" rowspan="1">Webex Events Webcasts (Attendees only)</td><td colspan="1" rowspan="1">*.vbrickrev.com</td></tr><tr><td colspan="1" rowspan="1">Used for Slido PPT add-in and to allow Slido webpages to create polls/quizzes in pre-meeting</td><td colspan="1" rowspan="1">*.slido.com<br/>			*.sli.do<br/>			*.data.logentries.com</td></tr><tr><td colspan="1" rowspan="1">If you have Webex app Desktop Clients, Cloud Registered Devices (including Webex Boards) connecting to Webex Meetings, you also need to allow the list of domains outlined in <a href="https://help.webex.com/WBX000028782/Network-Requirements-for-Webex-Teams-Services">https://help.webex.com/WBX000028782/Network-Requirements-for-Webex-Teams-Services</a></td><td colspan="1" rowspan="1"> </td></tr></tbody></table>
All Webex hosted services are advertised under AS13445, refer to the <a href="https://www.webex.com/peering-policy.html">Webex Peering Policy</a>. Services hosted by other service providers are not included here.  This includes TSP partner systems or our content delivery partners.  If you are connecting to partner-hosted systems such as a Partner VoIP system, please contact the partner for the appropriate IP addresses and ports.<br/><br/><b>Guidance on IPS firewall:</b>
<ul><li>Bypass firewall IPS or other types of DoS protection(allowed) for Webex traffic (defined by Webex IP CIDR blocks), especially the media traffic.</li><li>If IPS can not be a bypass, proper sizing is required to be carried out to ensure IPS have sufficient capacity to handle the audio and video throughput for a large number of participants.</li><li>If IPS can not be a bypass, proper fine-tuning of the signature and threshold has to be achieved so that Webex traffic is not misclassified and subsequently dropped.</li><li>Monitor firewall IPS alerts to investigate any IPS alert against Webex traffic.</li></ul>
Note: The following UserAgents will be passed by Webex by the utiltp process in Webex, and should be allowed through an agency's firewall:'''


def testgrab_domain_table():
    """
    Given:
        -Raw list of lists that contains ips CIDR and net range, returned by api call:
        first array is the title, 2 seconds arrays are data, last array is message.
    When:
        - Filtered list contains domain's urls only
    Then:
        - Return CIDR ips list without errors
    """
    from CiscoWebExFeed import grab_domain_table
    expected_result = ['0.0.0.0/0', '8.8.8.8/8']
    assert grab_domain_table(html_section) == expected_result
