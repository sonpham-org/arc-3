"""a027 Echo Effector -- bind commands to delayed physical effects, not immediate flashes."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,STAGE,COMMAND,FLASH,EFFECT,QUEUE,CLOCK,GOAL,BAD=6,10,14,11,12,8,5,13,15
LEVELS=[{"name":"Decoy Flash","seq":(1,3)},{"name":"Second Command","seq":(2,3)},{"name":"Delayed Effect","seq":(1,2,3)},{"name":"Timing Compare","seq":(4,2,1,3)},{"name":"Causal Binding","seq":(2,3,1,4,2,1,3)},{"name":"Echo Effector","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 tick,queue,effects,flashes,observations,bound=s;q=list(queue);e=list(effects)
 if a in (1,2):q.append((tick+2+a,a));flashes=flashes+((tick,(a*3+tick)%8),)
 elif a==3:
  tick+=1;due=[item for item in q if item[0]<=tick];q=[item for item in q if item[0]>tick]
  for _,cmd in due:e[cmd-1]=(e[cmd-1]+cmd+tick)%8
  observations=observations+((tick,tuple(q),tuple(e),flashes[-2:]),)
 elif a==4:tick+=2;observations=observations+((tick,tuple(q),tuple(e),flashes[-3:]),)
 elif a==5:bound=(tick,tuple(q),tuple(e),flashes[-4:],observations[-4:])
 return tick,tuple(q),tuple(e),flashes,observations,bound
for x in LEVELS:
 s=(0,(),(0,4),(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=STAGE
  for i,p in enumerate(g.effects):x=9+i*28;f[10:31,x:x+20]=EFFECT;f[23-p*2:29,x+4:x+16]=COMMAND
  for i,(_,p) in enumerate(g.flashes[-4:]):x=8+i*12;f[37:43,x:x+9]=FLASH;f[44:47,x:x+2+p%6]=COMMAND
  for i,_ in enumerate(g.queue):f[49:54,8+i*12:17+i*12]=QUEUE
  f[55:59,8:8+(g.tick%6)*8+7]=CLOCK
  if g.bound:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A027(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a027",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.tick=0;self.queue=();self.effects=(0,4);self.flashes=self.observations=();self.bound=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.tick,self.queue,self.effects,self.flashes,self.observations,self.bound=advance((self.tick,self.queue,self.effects,self.flashes,self.observations,self.bound),a)
  elif a==6:
   if (self.tick,self.queue,self.effects,self.flashes,self.observations,self.bound)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
