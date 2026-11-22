"""
Test that an interrupt stops the expression parser while it looks up the
declarations of the frame's namespaces, that the expression then fails without
running, and that only the interrupted debugger is affected.
"""

import lldb
from lldbsuite.test.decorators import *
from lldbsuite.test.lldbtest import *
from lldbsuite.test import lldbutil


@requireExpressionEvaluation
class TestInterruptDeclLookup(TestBase):
    def test(self):
        self.build()
        (target, _, thread, _) = lldbutil.run_to_source_breakpoint(
            self, "// break here", lldb.SBFileSpec("main.cpp")
        )
        callee_frame = thread.GetFrameAtIndex(0)
        caller_frame = thread.GetFrameAtIndex(1)

        other = lldb.SBDebugger.Create(False)

        def cleanup():
            if self.dbg.InterruptRequested():
                self.dbg.CancelInterruptRequest()
            if other.InterruptRequested():
                other.CancelInterruptRequest()
            lldb.SBDebugger.Destroy(other)

        self.addTearDownHook(cleanup)

        exe = target.GetExecutable()
        other_target = other.CreateTarget(exe.fullpath)
        self.assertEqual(other_target.FindModule(exe), target.FindModule(exe))

        # Evaluating in the callee looks up 'value' in 'second', whose
        # declarations have not been parsed yet. An interrupt requested of
        # another debugger using the same module must not stop that.
        other.RequestInterrupt()
        result = callee_frame.EvaluateExpression("value")
        other.CancelInterruptRequest()
        self.assertSuccess(result.GetError())
        self.assertEqual(result.GetValueAsSigned(), 2)

        # With this debugger's interrupt requested, looking up names from the
        # caller stops while parsing the declarations in 'first', and the
        # expression fails without calling 'bump' or declaring '$Declared'.
        self.dbg.RequestInterrupt()
        result = caller_frame.EvaluateExpression("struct $Declared { int i; }; bump()")
        self.assertFailure(result.GetError())
        self.assertIn(
            "Interrupted while parsing expression", result.GetError().GetCString()
        )
        result = caller_frame.EvaluateExpression("value")
        self.assertFailure(result.GetError())
        self.dbg.CancelInterruptRequest()
        self.assertEqual(
            caller_frame.EvaluateExpression("g_counter").GetValueAsSigned(), 0
        )
        self.assertFailure(
            caller_frame.EvaluateExpression("sizeof($Declared)").GetError()
        )

        # Once the interrupt is over, the same expressions bind to the right
        # declarations: 'value' is first::value, not ::value or second::value.
        self.assertEqual(caller_frame.EvaluateExpression("value").GetValueAsSigned(), 1)
        result = caller_frame.EvaluateExpression("struct $Declared { int i; }; bump()")
        self.assertSuccess(result.GetError())
        self.assertEqual(result.GetValueAsSigned(), 1)
