// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {LandRegistryAnchor} from "./LandRegistryAnchor.sol";

/// @title MultiSigRegistrar — k-of-n custody wrapper for LandRegistryAnchor
/// @notice Replaces single-key registrar custody with a threshold-signature
///         arrangement. Production deployments seat five named signers:
///         (1) MoLHUD Commissioner Land Registration, (2) NITA-U Security Lead,
///         (3) District Land Board chair, (4) LandGuard project signer,
///         (5) Independent auditor / civil-society observer. Three of five
///         must confirm any batch commit; no single party can anchor alone.
/// @dev    Gas-cheap and audit-friendly: every confirmation emits an event,
///         every execution emits an event, every batch is its own proposal.
contract MultiSigRegistrar {
    LandRegistryAnchor public immutable anchor;
    uint8 public immutable threshold;
    address[] public signers;
    mapping(address => bool) public isSigner;

    struct Proposal {
        uint16 districtId;
        bytes32 batchId;
        bytes32 merkleRoot;
        uint8 confirmations;
        bool executed;
        uint64 proposedAt;
    }

    mapping(bytes32 => Proposal) public proposals;
    mapping(bytes32 => mapping(address => bool)) public confirmed;

    event SignerAdded(address indexed signer);
    event ProposalCreated(
        bytes32 indexed proposalId,
        uint16 indexed districtId,
        bytes32 indexed batchId,
        bytes32 merkleRoot,
        address proposer
    );
    event ProposalConfirmed(
        bytes32 indexed proposalId,
        address indexed signer,
        uint8 confirmations
    );
    event ProposalExecuted(bytes32 indexed proposalId, bytes32 indexed batchId);

    error NotASigner();
    error AlreadyConfirmed();
    error AlreadyExecuted();
    error UnknownProposal();
    error InvalidThreshold();
    error InsufficientSigners();

    constructor(address[] memory _signers, uint8 _threshold, address _anchor) {
        if (_signers.length < _threshold || _threshold == 0) revert InvalidThreshold();
        if (_signers.length < 3) revert InsufficientSigners(); // sane floor
        anchor = LandRegistryAnchor(_anchor);
        threshold = _threshold;
        for (uint256 i = 0; i < _signers.length; i++) {
            address s = _signers[i];
            if (s == address(0) || isSigner[s]) revert InvalidThreshold();
            isSigner[s] = true;
            signers.push(s);
            emit SignerAdded(s);
        }
    }

    /// @notice Compute the deterministic ID for a proposal.
    /// @dev    Same (districtId, batchId, merkleRoot) tuple always produces the
    ///         same proposalId — repeat proposals add confirmations rather
    ///         than creating duplicates.
    function proposalIdOf(
        uint16 districtId,
        bytes32 batchId,
        bytes32 merkleRoot
    ) public pure returns (bytes32) {
        return keccak256(abi.encode(districtId, batchId, merkleRoot));
    }

    /// @notice Propose AND confirm in a single call. Used by every signer.
    /// @dev    The first call materialises the proposal; subsequent calls add
    ///         confirmations; the call that crosses the threshold executes
    ///         ``anchor.commitBatch`` atomically.
    function proposeAndConfirm(
        uint16 districtId,
        bytes32 batchId,
        bytes32 merkleRoot
    ) external returns (bytes32 proposalId) {
        if (!isSigner[msg.sender]) revert NotASigner();
        proposalId = proposalIdOf(districtId, batchId, merkleRoot);
        Proposal storage p = proposals[proposalId];
        if (p.executed) revert AlreadyExecuted();
        if (confirmed[proposalId][msg.sender]) revert AlreadyConfirmed();
        if (p.proposedAt == 0) {
            p.districtId = districtId;
            p.batchId = batchId;
            p.merkleRoot = merkleRoot;
            p.proposedAt = uint64(block.timestamp);
            emit ProposalCreated(proposalId, districtId, batchId, merkleRoot, msg.sender);
        }
        confirmed[proposalId][msg.sender] = true;
        unchecked {
            p.confirmations += 1;
        }
        emit ProposalConfirmed(proposalId, msg.sender, p.confirmations);
        if (p.confirmations >= threshold) {
            p.executed = true;
            anchor.commitBatch(districtId, batchId, merkleRoot);
            emit ProposalExecuted(proposalId, batchId);
        }
    }

    function signersList() external view returns (address[] memory) {
        return signers;
    }
}
