// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

/// @notice Educational, transparent ballot. It does not provide ballot secrecy or sybil resistance.
contract Ballot {
    enum Phase {
        Setup,
        Open,
        Ended,
        Closed
    }

    error NotOwner();
    error InvalidWindow();
    error InvalidCandidateSet();
    error SetupClosed();
    error InvalidVoter();
    error Ineligible();
    error AlreadyVoted();
    error InvalidCandidate();
    error BallotNotOpen();
    error TooEarlyToClose();
    error AlreadyClosed();

    address public immutable owner;
    uint64 public immutable opensAt;
    uint64 public immutable closesAt;
    string[] private candidateNames;
    mapping(address => bool) public eligible;
    mapping(address => bool) public hasVoted;
    mapping(address => uint256) public selectedCandidate;
    mapping(uint256 => uint256) public voteCounts;
    uint256 public eligibleCount;
    uint256 public totalVotes;
    bool public closed;

    event VoterAdded(address indexed voter);
    event VoteCast(address indexed voter, uint256 indexed candidateId);
    event BallotClosed(address indexed closer, uint256 timestamp);

    modifier onlyOwner() {
        if (msg.sender != owner) revert NotOwner();
        _;
    }

    constructor(string[] memory candidates, uint64 startTime, uint64 endTime) {
        if (startTime <= block.timestamp || endTime <= startTime) revert InvalidWindow();
        if (candidates.length < 2 || candidates.length > 16) revert InvalidCandidateSet();
        for (uint256 i = 0; i < candidates.length; ++i) {
            if (bytes(candidates[i]).length == 0 || bytes(candidates[i]).length > 64) revert InvalidCandidateSet();
            for (uint256 j = 0; j < i; ++j) {
                if (keccak256(bytes(candidates[i])) == keccak256(bytes(candidates[j]))) revert InvalidCandidateSet();
            }
            candidateNames.push(candidates[i]);
        }
        owner = msg.sender;
        opensAt = startTime;
        closesAt = endTime;
    }

    function addEligibleVoter(address voter) external onlyOwner {
        if (closed || block.timestamp >= opensAt) revert SetupClosed();
        if (voter == address(0) || eligible[voter]) revert InvalidVoter();
        eligible[voter] = true;
        ++eligibleCount;
        emit VoterAdded(voter);
    }

    function vote(uint256 candidateId) external {
        if (closed || block.timestamp < opensAt || block.timestamp >= closesAt) revert BallotNotOpen();
        if (!eligible[msg.sender]) revert Ineligible();
        if (hasVoted[msg.sender]) revert AlreadyVoted();
        if (candidateId >= candidateNames.length) revert InvalidCandidate();
        hasVoted[msg.sender] = true;
        selectedCandidate[msg.sender] = candidateId;
        ++voteCounts[candidateId];
        ++totalVotes;
        emit VoteCast(msg.sender, candidateId);
    }

    function close() external onlyOwner {
        if (closed) revert AlreadyClosed();
        if (block.timestamp < closesAt) revert TooEarlyToClose();
        closed = true;
        emit BallotClosed(msg.sender, block.timestamp);
    }

    function candidateCount() external view returns (uint256) {
        return candidateNames.length;
    }

    function candidateName(uint256 candidateId) external view returns (string memory) {
        if (candidateId >= candidateNames.length) revert InvalidCandidate();
        return candidateNames[candidateId];
    }

    function phase() external view returns (Phase) {
        if (closed) return Phase.Closed;
        if (block.timestamp < opensAt) return Phase.Setup;
        if (block.timestamp < closesAt) return Phase.Open;
        return Phase.Ended;
    }
}
