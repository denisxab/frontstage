# The Real Problems with Backstage

The main drawback — one that overshadows all its openness and flexibility — is that Backstage is 93% frontend technology.

What's the problem? Ask yourself: who in your company will actually deploy and maintain Backstage? Probably not a specially hired expert, but the nearest available person. In 98% of cases that's a DevOps engineer — and in 99% of cases, they don't know frontend development. Without that knowledge, Backstage's openness and modularity become meaningless: there's simply no one to leverage them. Unless you plan to teach your DevOps engineers React?

If Backstage had been built on a DevOps-friendly stack, the story would be different. Then a "developer portal" could be configured and maintained by the same people who manage the infrastructure — without the fear of a bus factor.

[github.com/backstage/backstage](https://github.com/backstage/backstage)

> Sure, Node.js and TypeScript are general-purpose technologies, not purely frontend. But I suspect DevOps engineers would chuckle at that argument.

> Sure, some companies have Platform Engineering teams with a full frontend stack. But for the 80% of companies that don't even have dedicated DevOps engineers, that's not a valid counterargument.

## System Requirements They Don't Advertise

Backstage consumes resources that are wildly disproportionate to the tasks it's designed for.

Official minimum requirements:

- 20 GB disk space
- 6 GB RAM

Notably, only minimum requirements are published — recommended specs are nowhere to be found.

No surprise: the reality is far more alarming. Based on real-world experience, recommended requirements for a team of 100–200 people are:

- 4–8 CPU
- 16 GB RAM
- 50–100 GB disk space

You might say: "Just get a bigger VPS and it'll work." But that leads to the next problem.

### Local Development

Backstage won't run locally on an average work laptop. In practice, everyone who works with Backstage — testing features, writing plugins, fixing bugs — needs a machine on the level of a high-end MacBook Pro.

> Of course, Backstage can be configured through out-of-the-box settings — there's a lot there. But anyone who has actually deployed it in production will hear that argument with a tired smile.

For small and medium businesses, this isn't just a friction point — it's a blocker. Management will shut down the Backstage initiative, and the team will go back to their old Confluence pages.

[backstage.io/docs/getting-started](https://backstage.io/docs/getting-started/)

## Conclusion

Backstage markets itself as an "open framework for building developer portals." But its openness runs into architectural decisions that make real-world adoption complex and expensive.

Companies with large budgets and dedicated Platform Engineering teams can afford Backstage. For small and medium businesses, it's practically out of reach. Backstage may want to become simpler and more accessible, but its architecture makes that impossible.
