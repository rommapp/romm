from handler.socket_handler import netplay_socket_handler, socket_handler


def test_netplay_cannot_join_the_main_servers_rooms():
    # Netplay clients are unauthenticated and name their own rooms, so an emit to
    # `user:{id}` or `admin` must not reach a netplay socket that picked that name.
    netplay = netplay_socket_handler.socket_server.manager
    main = socket_handler.socket_server.manager
    assert netplay.channel != main.channel
