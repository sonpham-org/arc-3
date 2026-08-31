"""q741 Aurora Obligation -- trace a delayed consequence to causal identity."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,OBSERVATORY,CURTAIN,MOTE,REWARD,OBLIGATION,HYSTERESIS,TERMINAL,BAD=7,10,12,14,6,11,5,4,15
LEVELS=[{"name":"One Reward","rewards":1,"plan":(1,4,5)},{"name":"Moved Mote","rewards":2,"plan":(2,4,1,5)},{"name":"Hidden Debtor","rewards":3,"plan":(3,4,1,2,5)},{"name":"Intervening Gain","rewards":4,"plan":(1,4,2,4,3,5)},{"name":"Hysteretic Debt","rewards":5,"plan":(2,4,1,3,4,2,5)},{"name":"Aurora Obligation","rewards":6,"plan":(3,4,1,2,4,3,1,5)}]
def advance(s,a,x):
 entities,obligation,rewards,control,hyst,terminal=s;entities=[list(e) for e in entities];rewards=list(rewards)
 if a in (1,2,3):
  i=a-1
  if obligation is None:obligation=(entities[i][0],(a+hyst)%4)
  else:entities[i][1]=(entities[i][1]+a+control+hyst)%4;rewards.append((entities[i][0],a,len(rewards)))
 elif a==4:rewards.append((0,control,hyst));control=(control-1)%3;hyst=(hyst+2+control)%5
 elif a==5:
  if obligation is None or len(rewards)<x["rewards"]:return None
  ident,effect=obligation;target=next(e for e in entities if e[0]==ident);target[1]=(target[1]+effect+hyst)%4;terminal=(ident,effect,tuple(tuple(e) for e in entities),tuple(rewards),hyst)
 return tuple(tuple(e) for e in entities),obligation,tuple(rewards),control,hyst,terminal
def target_state(x):
 s=(((1,0),(2,1),(3,2)),None,(),0,0,None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=OBSERVATORY;f[8:31,7:57]=CURTAIN
  for i,(ident,look) in enumerate(g.entities):x=9+i*17;f[12:20,x:x+13]=MOTE-look;f[21:23,x:x+2+ident]=OBLIGATION
  f[36:39,8:11+(len(g.rewards)%6)*8]=REWARD;f[44:47,8:11+g.hyst*9]=HYSTERESIS;f[54:57,40:56]=TERMINAL if g.terminal else CURTAIN
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q741(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target_state=target_state(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q741",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.entities=((1,0),(2,1),(3,2));self.obligation=None;self.rewards=();self.control=self.hyst=0;self.terminal=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target_state=target_state(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.entities,self.obligation,self.rewards,self.control,self.hyst,self.terminal),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.entities,self.obligation,self.rewards,self.control,self.hyst,self.terminal=s
  elif a==6:
   if (self.entities,self.obligation,self.rewards,self.control,self.hyst,self.terminal)==self.target_state:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
