import simpy

def car(env):
    print("Car arrives at", env.now)
    yield env.timeout(5)
    print("Car leaves at", env.now)

def main():
    env = simpy.Environment()
    env.process(car(env))
    env.run(until=10)

if __name__ == "__main__":
    main()