"""q160 Tool Metamorphosis -- transfer a mechanical relation into agent coordination."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,SHOP,PART,TOOL,AGENT,RELATION,COMMAND,GOAL,BAD=4,10,9,14,6,11,5,7,15
LEVELS=[{"name":"Paired Lever","relation":1,"plan":(1,2,4,3,5)},{"name":"Three-Part Tool","relation":2,"plan":(2,3,1,4,2,5)},{"name":"Agent Copy","relation":3,"plan":(1,3,2,4,1,2,5)},{"name":"Social Lever","relation":1,"plan":(2,1,4,3,2,1,5)},{"name":"Crossed Roles","relation":2,"plan":(1,2,3,4,3,1,2,5)},{"name":"Tool Metamorphosis","relation":3,"plan":(3,1,2,1,4,2,3,1,2,5)}]
def advance(s,a,x):
 parts,agents,commands,coordinated=s;parts=list(parts);commands=list(commands)
 if a in (1,2,3):
  if agents is None:parts.append((a,(a*x["relation"]+len(parts))%5))
  else:commands.append((a,(a+x["relation"]+len(commands))%4))
 elif a==4:
  if agents is not None or len(parts)<2:return None
  agents=tuple((i,p[0],p[1]) for i,p in enumerate(parts));parts=[]
 elif a==5:
  if agents is None or not commands:return None
  coordinated=(x["relation"],agents,tuple(commands),sum(v for _,v in commands)%5)
 return tuple(parts),agents,tuple(commands),coordinated
def target(x):
 s=((),None,(),None)
 for a in x["plan"]:s=advance(s,a,x);assert s is not None
 return s
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=SHOP;f[8:28,8:22]=PART;f[8:28,25:39]=TOOL;f[8:28,42:56]=AGENT
  for i,p in enumerate(g.parts[:6]):x=8+(i%3)*18;y=10+(i//3)*11;f[y:y+7,x:x+12]=PART-p[0]
  if g.agents:
   for i,(_,_,v) in enumerate(g.agents[:6]):x=8+(i%3)*18;y=10+(i//3)*11;f[y:y+7,x:x+12]=AGENT-v
  for i,(_,v) in enumerate(g.commands[-6:]):f[36+i*3:38+i*3,8:11+v*11]=COMMAND
  f[53:56,8:24]=RELATION;f[56:59,44:56]=GOAL
  if g.bad:f[61:64,20:44]=BAD
  return f
class Q160(ARCBaseGame):
 def __init__(self):self.display=D(self);self.bad=False;self._reset();self.target=target(LEVELS[0]);ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("q160",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.parts=();self.agents=None;self.commands=();self.coordinated=None
 def on_set_level(self,l):self._reset();self.bad=False;self.target=target(LEVELS[self.level_index])
 def step(self):
  a=self.action.id.value;x=LEVELS[self.level_index]
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):
   s=advance((self.parts,self.agents,self.commands,self.coordinated),a,x)
   if s is None:self.bad=True;self.lose()
   else:self.parts,self.agents,self.commands,self.coordinated=s
  elif a==6:
   if (self.parts,self.agents,self.commands,self.coordinated)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
