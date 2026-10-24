using NUnit.Framework;
using UnityEngine;

namespace RelayArena.Tests
{
    public sealed class RelayRulesTests
    {
        [TestCase(0f, 2f, true)]
        [TestCase(2f, 2f, true)]
        [TestCase(2.01f, 2f, false)]
        [TestCase(-1f, 2f, false)]
        public void CaptureRangeHasClosedBoundary(float distance, float radius, bool expected)
        {
            Assert.That(RelayRules.CanCapture(distance, radius), Is.EqualTo(expected));
        }

        [Test]
        public void CaptureRejectsNonFiniteValues()
        {
            Assert.That(RelayRules.CanCapture(float.NaN, 2f), Is.False);
            Assert.That(RelayRules.CanCapture(1f, float.PositiveInfinity), Is.False);
        }

        [Test]
        public void MovementInputIsClampedAndRejectsNonFiniteValues()
        {
            Assert.That(RelayRules.ClampInput(new Vector2(3f, 4f)).magnitude, Is.EqualTo(1f).Within(0.0001f));
            Assert.That(RelayRules.ClampInput(new Vector2(float.NaN, 1f)), Is.EqualTo(Vector2.zero));
        }

        [Test]
        public void TeamsAreAssignedDeterministically()
        {
            Assert.That(RelayRules.TeamForClient(0), Is.Zero);
            Assert.That(RelayRules.TeamForClient(1), Is.EqualTo(1));
            Assert.That(RelayRules.TeamForClient(2), Is.Zero);
        }
    }
}
