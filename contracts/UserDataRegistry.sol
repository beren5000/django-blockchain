// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract UserDataRegistry {
    // Struct to store user data
    struct UserData {
        string imageReference; // IPFS hash or URL to the image
        uint256 timestamp;    // When the data was last updated
        bool exists;          // Flag to check if data exists
    }
    
    // Mapping to track authorized users
    mapping(address => bool) public authorizedUsers;
    
    // Mapping to store user data
    mapping(address => UserData) public userData;
    
    // Contract admin
    address public admin;
    
    // Events
    event UserDataUpdated(address indexed user, string imageReference, uint256 timestamp);
    event UserAuthorized(address indexed user);
    event UserDeauthorized(address indexed user);
    
    // Constructor to initialize the contract with authorized users
    constructor(address[] memory _authorizedUsers) {
        admin = msg.sender;
        
        // Add all authorized users
        for (uint i = 0; i < _authorizedUsers.length; i++) {
            _authorizeUser(_authorizedUsers[i]);
        }
    }
    
    // Modifier to restrict access to authorized users
    modifier onlyAuthorized() {
        require(authorizedUsers[msg.sender], "Not authorized to update data");
        _;
    }
    
    // Modifier to restrict access to the admin
    modifier onlyAdmin() {
        require(msg.sender == admin, "Not the contract admin");
        _;
    }
    
    // Function to update user data - only callable by authorized users
    function updateUserData(string memory _imageReference) external onlyAuthorized {
        userData[msg.sender] = UserData({
            imageReference: _imageReference,
            timestamp: block.timestamp,
            exists: true
        });
        
        emit UserDataUpdated(msg.sender, _imageReference, block.timestamp);
    }
    
    // Function to get user data for any address
    function getUserData(address _user) external view returns (string memory imageReference, uint256 timestamp, bool exists) {
        UserData memory data = userData[_user];
        return (data.imageReference, data.timestamp, data.exists);
    }
    
    // Function to check if an address is authorized
    function isAuthorized(address _user) external view returns (bool) {
        return authorizedUsers[_user];
    }
    
    // Function to authorize a new user (admin only)
    function authorizeUser(address _user) external onlyAdmin {
        _authorizeUser(_user);
    }
    
    // Internal function to authorize a user
    function _authorizeUser(address _user) internal {
        require(_user != address(0), "Cannot authorize zero address");
        authorizedUsers[_user] = true;
        emit UserAuthorized(_user);
    }
    
    // Function to deauthorize a user (admin only)
    function deauthorizeUser(address _user) external onlyAdmin {
        require(_user != address(0), "Cannot deauthorize zero address");
        authorizedUsers[_user] = false;
        emit UserDeauthorized(_user);
    }
    
    // Function to get all data for a list of users (batch query)
    function getUsersData(address[] calldata _users) external view 
        returns (string[] memory imageReferences, uint256[] memory timestamps, bool[] memory dataExists) {
        
        uint256 length = _users.length;
        imageReferences = new string[](length);
        timestamps = new uint256[](length);
        dataExists = new bool[](length);
        
        for (uint256 i = 0; i < length; i++) {
            UserData memory data = userData[_users[i]];
            imageReferences[i] = data.imageReference;
            timestamps[i] = data.timestamp;
            dataExists[i] = data.exists;
        }
        
        return (imageReferences, timestamps, dataExists);
    }
}