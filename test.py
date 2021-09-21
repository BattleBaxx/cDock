import blessed
import docker

client = docker.from_env()
container_list = client.containers.list()
print(container_list[1].status)
print(container_list[1].name)
print(container_list[1].id)
print(container_list[1].stats(stream=True))
# obj = container_list[1].stats(stream=True)
# for x in obj:
#     print(x)
# print(container_list[1].stats(stream=True))
print(container_list[1].image)
# https://stackoverflow.com/questions/63834065/is-there-a-way-to-obtain-the-date-when-the-docker-image-was-created-using-docker
# print(client.inspect_container(container_list[1].id)['NetworkSettings']['Ports'])
