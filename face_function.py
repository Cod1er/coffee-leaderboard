import boto3
import json
import time

rekognition = boto3.client('rekognition')
dynamodb = boto3.client('dynamodb')
s3_client = boto3.client('s3')

FACE_COLLECTION = "Faces"
FACE_MATCH_THRESHOLD = 70



def lambda_handler(event, context):
    bucket = event['mybucket']
    key = event['mykey']

    img = {
        'S3Object': {
            'Bucket': bucket,
            'Name': key, }
    }

    time_now = str(int(time.time()))

    # Checks if user is already registered
    faces = rekognition.search_faces_by_image(CollectionId=FACE_COLLECTION, Image=img,
                                              FaceMatchThreshold=FACE_MATCH_THRESHOLD, MaxFaces=1)

    if len(faces['FaceMatches']) == 1:  # User is already registered in the collection
        # Authenticate
        faceid = faces['FaceMatches'][0]['Face']['FaceId']
        item = dynamodb.get_item(TableName='faces', Key={'faceID': {'S': str(faceid)}})

        # Gets the item
        print(item)
        item = item['Item']
        face_id = item['faceID']['S']
        score = int(item['score']['S'])
        unixtime = int(item['unixtime']['S'])

        inc = str(score + 1)
        time_now = int(time.time())
        time_10_minutes_ago = time_now - 300
        if unixtime < time_10_minutes_ago:
            dynamodb.update_item(TableName='faces', Key={'faceID': {'S': str(face_id)}},
                                 UpdateExpression="set score = :val, unixtime =:val2, pathToImage=:val3",
                                 ExpressionAttributeValues={
                                     ':val': {'S': inc},
                                     ':val2': {'S': str(time_now)},
                                     ':val3': {'S': key}
                                 }
                                 )
            dynamodb.put_item(
                TableName='logs',
                Item={
                    'unixtime': {'S': str(time_now)},
                    'mymess': {'S': 'User Score increased to ' + inc}
                })
            return "User Score increased"
        else:
            dynamodb.put_item(
                TableName='logs',
                Item={
                    'unixtime': {'S': time_now},
                    'mymess': {'S': 'Sorry, you can only participate every 5 minutes.)'}
                })
            return "You can only participate every 5 minutes, sorry mate"
    else:
        # Face not found in the Rekognition database
        faces = rekognition.index_faces(Image=img, CollectionId=FACE_COLLECTION)

        # Check if there are no faces in the image:
        if len(faces['FaceRecords']) == 0:

            dynamodb.put_item(  # log
                TableName='logs',
                Item={
                    'unixtime': {'S': time_now},
                    'mymess': {'S': "No faces were found in the picture"}
                })

            return json.dumps({
                'success': False,
                'message': 'No face found in the image'
            })

        # More than one face in the image:
        elif len(faces['FaceRecords']) > 1:
            rekognition.delete_faces(CollectionId=FACE_COLLECTION,
                                     FaceIds=[f['Face']['FaceId'] for f in faces['FaceRecords']])

            dynamodb.put_item(
                TableName='logs',
                Item={
                    'unixtime': {'S': time_now},
                    'mymess': {'S': "Error: More than one face detected in the image... Destruction in progress"}
                })

            return json.dumps({
                'success': False,
                'message': 'More than one face in the image'
            })

        # One new face in the image, register it:
        else:
            face_id = faces['FaceRecords'][0]['Face']['FaceId']
            dynamodb.put_item(
                TableName='faces',
                Item={
                    'faceID': {'S': face_id},
                    'score': {'S': '1'},
                    'unixtime': {'S': str(int(time.time()))},
                    'pathToImage': {'S': str(key)}
                })

            response = dynamodb.put_item(
                TableName='logs',
                Item={
                    'unixtime': {'S': time_now},
                    'mymess': {'S': "Congratulations! You're now registered for the coffee leaderboard."}
                })

            return response
