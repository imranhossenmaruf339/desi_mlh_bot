import pymongo
from pymongo import MongoClient

class VideoControl:
    def __init__(self, mongo_uri):
        self.client = MongoClient(mongo_uri)
        self.db = self.client['video_control_db']
        self.collection = self.db['group_video_states']

    def turn_on(self, group_id):
        self.collection.update_one({'group_id': group_id}, {'$set': {'video_on': True}}, upsert=True)

    def turn_off(self, group_id):
        self.collection.update_one({'group_id': group_id}, {'$set': {'video_on': False}}, upsert=True)

    def get_video_state(self, group_id):
        state = self.collection.find_one({'group_id': group_id})
        return state['video_on'] if state else None

# Example usage
if __name__ == "__main__":
    video_control = VideoControl('mongodb://localhost:27017/')
    group_id = 'example_group_id'
    
    video_control.turn_on(group_id)
    print(f"Video state for {group_id}: {video_control.get_video_state(group_id)}")
    
    video_control.turn_off(group_id)
    print(f"Video state for {group_id}: {video_control.get_video_state(group_id)}")
