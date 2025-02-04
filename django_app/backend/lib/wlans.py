import requests
import json
import logging
from .common import Common


class Wlan(Common):

    def pull(self, body):
        body = self.get_body(body)
        if "site_id" in body:
            logging.debug("new site_id request")
            return self._get_wlans(body, "sites", "site_id")
        elif "org_id" in body:
            logging.debug("new org_id request")
            return self._get_wlans(body, "orgs", "org_id")
        else:
            logging.error(
                "new request without site_id not org_id: {0}".format(body))
            return {"status": 500, "data": {"message": "site_id or org_id missing"}}

    def _get_wlans(self, body, scope_name, scope_id_param):
        if scope_id_param in body:
            extract = self.extractAuth(body)
            if scope_name == "sites":
                url = "https://{0}/api/v1/sites/{1}/wlans/derived".format(
                    extract["host"], body[scope_id_param])
            elif scope_name == "orgs":
                url = "https://{0}/api/v1/orgs/{1}/wlans".format(
                    extract["host"], body[scope_id_param])
            if url:
                try:
                    logging.debug("REQ: {0}".format(url))
                    resp = requests.get(
                        url, headers=extract["headers"], cookies=extract["cookies"])
                    logging.debug("REQ: OK")
                    wlans = []
                    for wlan in resp.json():
                        if wlan['auth']["type"] == "psk":
                            if wlan["auth"].get("multi_psk_only") == True :
                                wlans.append(
                                    {"id": wlan["id"], "ssid": wlan["ssid"], "vlans": wlan.get("vlan_ids", [])})
                            elif type(wlan.get("dynamic_psk", None)) == dict and wlan.get("dynamic_psk").get("enabled") == True:
                                wlans.append(
                                    {"id": wlan["id"], "ssid": wlan["ssid"], "vlans": wlan.get("vlan_ids", [])})
                    return {"status": 200, "data": {"wlans": wlans}}
                except:
                    logging.error("REQ: _get_wlans NOK")
                    return {"status": 500, "data": {"message": "unable to retrieve the WLANs list"}}
            else:
                logging.warn(
                    "wrong or missing scope_name parameters in the request")
                return {"status": 500, "data": {"message": "missing {0} parameters in the request".format(scope_id_param)}}
        else:
            logging.warn(
                "missing {0} parameters in the request".format(scope_id_param))
            return {"status": 500, "data": {"message": "missing {0} parameters in the request".format(scope_id_param)}}   


    def _find_wlans(self, extract, ssid, scope_name, scope_id):
        url = "https://{0}/api/v1/{1}/{2}/wlans".format(
            extract["host"], scope_name, scope_id)
        logging.debug("REQ: {0}".format(url))
        resp = requests.get(
            url, headers=extract["headers"], cookies=extract["cookies"])
        logging.debug("REQ: OK")
        wlan_confs = []
        for wlan in resp.json():
            if wlan["ssid"] == ssid:
                wlan_confs.append(wlan)
        return wlan_confs

    def _get_wlan_by_id(self, extract, wlan_id, scope_name, scope_id):
        url = "https://{0}/api/v1/{1}/{2}/wlans/{3}".format(
            extract["host"], scope_name, scope_id, wlan_id)
        logging.debug("REQ: {0}".format(url))
        resp = requests.get(
            url, headers=extract["headers"], cookies=extract["cookies"])
        logging.debug("REQ: OK")
        return resp.json()

    def check_vlan(self, extract, ssid, new_vlan_id, scope_name, scope_id):
        result = []
        if new_vlan_id:
            wlan_confs = self._find_wlans(extract, ssid, scope_name, scope_id)
            '''
            "vlan_enabled": true,
            "vlan_id": null,
            "dynamic_vlan": null,
            "vlan_pooling": true,
            "vlan_ids": [10,20]
            '''
            if wlan_confs:
                for wlan_conf in wlan_confs:

                    vlan_enabled = wlan_conf["vlan_enabled"]
                    vlan_id = wlan_conf["vlan_id"]
                    vlan_ids = wlan_conf["vlan_ids"]
                    vlan_pooling = wlan_conf["vlan_pooling"]
                    dynamic_vlan = wlan_conf["dynamic_vlan"]
                    if not vlan_enabled:
                        result.append(
                            {"wlan_id": wlan_conf["id"], "reason": "VLAN tagging not enabled", "vlan_id": new_vlan_id, "scope_name": scope_name, "scope_id": scope_id, "code": "untagged"})
                    elif vlan_id and vlan_id != new_vlan_id:
                        result.append(
                            {"wlan_id": wlan_conf["id"], "reason": "WLAN configured with another VLAN ID", "vlan_id": new_vlan_id, "scope_name": scope_name, "scope_id": scope_id, "code": "static_vlan"})
                    elif dynamic_vlan and dynamic_vlan["enabled"] and not new_vlan_id in dynamic_vlan["vlans"]:
                        result.append(
                            {"wlan_id": wlan_conf["id"], "reason": "VLAN ID missing in dynamic VLAN list", "vlan_id": new_vlan_id, "scope_name": scope_name, "scope_id": scope_id, "code": "missing_in_dynamic"})
                    elif not vlan_pooling:
                        result.append(
                            {"wlan_id": wlan_conf["id"], "reason": "VLAN Pooling not enabled", "vlan_id": new_vlan_id, "scope_name": scope_name, "scope_id": scope_id, "code": "vlan_pool_disabled"})
                    elif not new_vlan_id in vlan_ids:
                        result.append(
                            {"wlan_id": wlan_conf["id"], "reason": "VLAN ID missing in VLAN pool list", "vlan_id": new_vlan_id, "scope_name": scope_name, "scope_id": scope_id, "code": "missing_in_pool"})
        return result

    def change_vlan(self, body):
        # host: this.host, cookies: this.cookies, headers: this.headers, vlan_check: vlan_chec
        body = self.get_body(body)
        extract = self.extractAuth(body)
        result = {
            "done": [],
            "error": []
        }
        if "vlan_check" in body:
            vlan_check = body["vlan_check"]
            wlan_conf = {}
            for check in vlan_check:
                if check["code"] in ["untagged", "vlan_pooling_disabled"]:
                    wlan_conf = {
                        "vlan_enabled": True,
                        "vlan_id": None,
                        "dynamic_vlan": None,
                        "vlan_pooling": True,
                        "vlan_ids": [1, check["vlan_id"]]
                    }
                elif check["code"] == "static_vlan":
                    wlan_conf = self._get_wlan_by_id(
                        extract, check["wlan_id"], check["scope_name"], check["scope_id"])
                    wlan_conf = {
                        "vlan_enabled": True,
                        "vlan_id": None,
                        "dynamic_vlan": None,
                        "vlan_pooling": True,
                        "vlan_ids": [wlan_conf["vlan_id"], check["vlan_id"]]
                    }
                elif check["code"] == "missing_in_dynamic":
                    wlan_conf = self._get_wlan_by_id(
                        extract, check["wlan_id"], check["scope_name"], check["scope_id"])
                    wlan_conf["dynamic_vlan"].append(check["vlan_id"])
                elif check["code"] == "missing_in_pool":
                    wlan_conf = self._get_wlan_by_id(
                        extract, check["wlan_id"], check["scope_name"], check["scope_id"])
                    wlan_conf["vlan_ids"].append(check["vlan_id"])

                try:
                    url = "https://{0}/api/v1/{1}/{2}/wlans/{3}".format(
                        extract["host"], check["scope_name"], check["scope_id"], check["wlan_id"])
                    logging.debug("REQ: {0}".format(url))
                    resp = requests.put(
                        url, headers=extract["headers"], cookies=extract["cookies"], json=wlan_conf)
                    logging.debug("REQ: OK")
                    result["done"].append(check["wlan_id"])
                except Exception as e:
                    print(e.__str__)
                    logging.debug("REQ: NOK")
                    result["error"].append(check["wlan_id"])

        return {"status": 200, "data": result}
