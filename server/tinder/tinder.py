import json
import logging
from datetime import datetime
from typing import Tuple, List
import random

import requests
from tinder.entities.update import Update
from tinder.entities.match import Match
from tinder.exceptions import Unauthorized, LoginException
from tinder.http import Http
from tinder.entities.user import UserProfile, LikePreview, Recommendation, SelfUser, LikedUser
import time 

class TinderClient:
    """
    The client can send requests to the Tinder API.
    """

    def __init__(self, auth_token: str, log_level: int = logging.INFO, ratelimit: int = 10):
        """
        Constructs a new client.

        :param auth_token: the <em>X-Auth-Token</em>
        :param log_level: the log level, default INFO
        :param ratelimit: the ratelimit multiplicator, default 10
        """

        self._http = Http(auth_token, log_level, ratelimit)
        self._self_user = None
        self._matches: dict = {}
        try:
            self._self_user = self.get_self_user()
        except Unauthorized:
            pass
        if self._self_user is None:
            raise LoginException()
        self.active = True
     

    def invalidate_match(self, match: Match):
        """
        Removes a match from the cache.

        :param match: the match to invalidate
        """

        self._matches.pop(match.id)

    def invalidate_self_user(self):
        """
        Invalidates the cached self user.
        """

        self._self_user = None

    def get_updates(self, last_activity_date: str = "") -> Update:
        """
        Gets updates from the Tinder API, such as new matches or new messages.

        :param last_activity_date:
        :return: updates from the Tinder API
        """

        if last_activity_date == "":
            last_activity_date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S.00Z")
        response = self._http.make_request(
            method="POST",
            route="/updates",
            body={"nudge": True, "last_activity_date": f"{last_activity_date}"},
        ).json()
        return Update(response)

    def get_recommendations(self) -> Tuple[Recommendation]:
        """
        Gets recommended users.

        :return: a tuple of recommended users
        """

        response = self._http.make_request(method="GET", route="/recs/core").json()
        return tuple(Recommendation(r, self._http) for r in response["results"])

    def get_like_previews(self) -> Tuple[LikePreview]:
        """
        Gets users that liked the self user.

        :return: a tuple of users that liked the self user
        """

        response = self._http.make_request(method="GET", route="/v2/fast-match/teasers").json()
        return tuple(LikePreview(user["user"], self._http) for user in response["data"]["results"])

    def load_all_matches(self, page_token: str = None) -> Tuple[Match]:
        """
        Gets all matches from the Tinder API.

        :return: a tuple of all matches
        """

        route = f"/v2/matches?count=60"
        if page_token:
            route = f"{route}&page_token={page_token}"

        data = self._http.make_request(method="GET", route=route).json()["data"]
        matches: List[Match] = list(Match(m, self._http, self) for m in data["matches"])
        if "next_page_token" in data:
            matches.extend(self.load_all_matches(data["next_page_token"]))

        self._matches.clear()
        for match in matches:
            self._matches.update(key=match.id, value=match)
        return tuple(matches)

    def get_match(self, match_id: str) -> Match:
        """
        Gets a match by id.

        :param match_id: the match id
        :return: a match by id
        """

        if match_id in self._matches:
            return self._matches[match_id]
        else:
            response = self._http.make_request(method="GET", route=f"/v2/matches/{match_id}").json()
            match = Match(response["data"], self._http, self)
            self._matches[match.id] = match
            return match

    def get_user_profile(self, user_id: str) -> UserProfile:
        """
        Gets a user profile by id.

        :param user_id: the user id
        :return: a user profile by id
        """

        response = self._http.make_request(method="GET", route=f"/user/{user_id}").json()
        return UserProfile(response["results"], self._http)

    def get_self_user(self) -> SelfUser:
        """
        Gets the self user.

        :return: the self user
        """

        if self._self_user is None:
            response = self._http.make_request(method="GET", route="/profile").json()
            return SelfUser(response, self._http)
        else:
            return self._self_user

    def get_liked_users(self) -> Tuple[LikedUser]:
        """
        Gets all users that the self user liked.

        :return: a tuple of all liked users
        """

        response = self._http.make_request(method="GET", route="/v2/my-likes").json()
        result = []
        for user in response["data"]["results"]:
            transformed = {}
            transformed.update(user.items())
            transformed.pop("type")
            transformed.pop("user")
            transformed.update(user["user"].items())
            result.append(transformed)
        return tuple(LikedUser(user, self._http) for user in result)
    
    def update_bio(self, new_bio: str) -> bool:
        """
        Updates the bio of the user's profile.

        :param new_bio: The new bio to set for the profile.
        :return: True if the update was successful, False otherwise.
        """
        payload = {
            "bio": new_bio
        }
        
        try:
            response = self._http.make_request(
                method="POST",  # Use POST or PUT as required by the API.
                route="/profile",  # The endpoint for profile updates; adjust if necessary.
                body=payload
            )
            
            if response.status_code == 200:
                return True
            else:
                logging.error(f"Failed to update bio. Status code: {response.status_code}")
                return False
        except Exception as e:
            logging.error(f"Exception occurred while updating bio: {e}")
            return False
    
    def swipe_routine(self, start_hour: int, end_hour: int, likes_per_day: int):
        """
        Executes a routine of swiping likes based on the specified time range and likes per day.

        :param start_hour: The hour to start the routine.
        :param end_hour: The hour to end the routine.
        :param likes_per_day: The maximum number of likes to perform in the routine.
        """
        print(start_hour,end_hour,likes_per_day)
        now = datetime.now()
        start_time = datetime(hour=start_hour,year=datetime.now().year,month=datetime.now().month,day=datetime.now().day)
        end_time = datetime(hour=end_hour,year=datetime.now().year,month=datetime.now().month,day=datetime.now().day)
      
        
        if start_time <= now <= end_time:
            likes_count = 0
            while likes_count < likes_per_day:
                recommendations = self.get_recommendations()
                for recommendation in recommendations:
                    recommendation.like()
                    print(recommendation)
                    likes_count += 1
                    if likes_count >= likes_per_day:
                        break
                    time.sleep(random.randint(1,5))  # Wait for 1ß5 seconds between likes to mimic human behavior
        else:
            print("Not within the swipe routine time.")

    def get_api_token(self,refresh_token):
        TOKEN_URL="https://api.gotinder.com/v2/auth/login/sms"
        data = {'refresh_token': refresh_token }
        r=self._http.make_request(route='/v2/auth/login/sms',method='POST',body=data,verify=False)
        #r = requests.post(TOKEN_URL, headers=self._http._headers, data=json.dumps(data), verify=False)
        print(r.url)
        response = r.json()
        return response.get("data")["api_token"]
    



