int g_counter = 0;
int bump() { return ++g_counter; }

int value = 0;

namespace second {
int value = 2;
int callee() {
  return value; // break here
}
} // namespace second

namespace first {
int value = 1;
int caller() { return second::callee(); }
} // namespace first

int main() { return first::caller(); }
