"""Default commands for JVM project types, keyed by build tool."""

INSTALL_CMDS: dict[str, str] = {
    "maven": "mvn install -DskipTests",
    "gradle": "./gradlew build -x test",
}

TEST_CMDS: dict[str, str] = {
    "maven": "mvn test",
    "gradle": "./gradlew test",
}

BUILD_CMDS: dict[str, str] = {
    "maven": "mvn package -DskipTests",
    "gradle": "./gradlew assemble",
}
