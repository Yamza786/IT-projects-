// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {Ballot} from "../src/Ballot.sol";

interface Vm {
    function warp(uint256 timestamp) external;
    function prank(address sender) external;
}

contract DuplicateBallotDeployer {
    function deploy(string[] memory names) external {
        new Ballot(names, 100, 200);
    }
}

contract BallotTest {
    Vm private constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));
    address private constant OWNER = address(0xA11CE);
    address private constant ALICE = address(0xB0B);
    address private constant BOB = address(0xCAFE);
    string[] private names;

    function setUp() public {
        names.push("North");
        names.push("South");
    }

    function createBallot() private returns (Ballot) {
        vm.prank(OWNER);
        return new Ballot(names, 100, 200);
    }

    function testOwnerCanCreateAndRegisterVotersBeforeOpen() public {
        Ballot ballot = createBallot();
        vm.prank(OWNER);
        ballot.addEligibleVoter(ALICE);
        require(ballot.eligible(ALICE), "voter should be eligible");
        require(ballot.eligibleCount() == 1, "eligible count should increment");
        require(uint256(ballot.phase()) == uint256(Ballot.Phase.Setup), "should be in setup");
    }

    function testOnlyEligibleAddressCanVoteOnce() public {
        Ballot ballot = createBallot();
        vm.prank(OWNER);
        ballot.addEligibleVoter(ALICE);
        vm.warp(100);
        vm.prank(ALICE);
        ballot.vote(1);
        require(ballot.voteCounts(1) == 1, "vote count should increment");
        require(ballot.totalVotes() == 1, "total votes should increment");
        require(ballot.hasVoted(ALICE), "voter should be recorded");
        vm.prank(ALICE);
        (bool secondVote,) = address(ballot).call(abi.encodeCall(ballot.vote, (0)));
        require(!secondVote, "second vote should fail");
    }

    function testRejectsUnregisteredAndInvalidCandidateVotes() public {
        Ballot ballot = createBallot();
        vm.prank(OWNER);
        ballot.addEligibleVoter(ALICE);
        vm.warp(100);
        vm.prank(BOB);
        (bool ineligible,) = address(ballot).call(abi.encodeCall(ballot.vote, (0)));
        require(!ineligible, "unregistered voter should fail");
        vm.prank(ALICE);
        (bool invalidCandidate,) = address(ballot).call(abi.encodeCall(ballot.vote, (2)));
        require(!invalidCandidate, "invalid candidate should fail");
    }

    function testSetupAndVotingWindowBoundaries() public {
        Ballot ballot = createBallot();
        vm.warp(100);
        vm.prank(OWNER);
        (bool lateRegistration,) = address(ballot).call(abi.encodeCall(ballot.addEligibleVoter, (ALICE)));
        require(!lateRegistration, "registration must close when voting opens");
        vm.warp(200);
        require(uint256(ballot.phase()) == uint256(Ballot.Phase.Ended), "ballot should have ended");
        vm.prank(OWNER);
        ballot.close();
        require(ballot.closed(), "ballot should close");
        require(uint256(ballot.phase()) == uint256(Ballot.Phase.Closed), "phase should be closed");
    }

    function testRejectsEarlyCloseAndNonOwnerClose() public {
        Ballot ballot = createBallot();
        vm.prank(OWNER);
        (bool early,) = address(ballot).call(abi.encodeCall(ballot.close, ()));
        require(!early, "early close should fail");
        vm.warp(200);
        vm.prank(ALICE);
        (bool unauthorized,) = address(ballot).call(abi.encodeCall(ballot.close, ()));
        require(!unauthorized, "non-owner close should fail");
    }

    function testRejectsDuplicateCandidateNames() public {
        string[] memory duplicateNames = new string[](2);
        duplicateNames[0] = "Same";
        duplicateNames[1] = "Same";
        DuplicateBallotDeployer deployer = new DuplicateBallotDeployer();
        (bool success,) = address(deployer).call(abi.encodeCall(deployer.deploy, (duplicateNames)));
        require(!success, "duplicate candidates should fail");
    }
}
