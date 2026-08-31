"""a032 Command Arbitration -- infer a stable priority rule among three controllers."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,PLATFORM,RAIL,PLAYER,AUTO,RESOLVED,BLOCKER,GOAL,BAD=1,10,8,14,11,12,6,13,15
LEVELS=[{"name":"One Conflict","seq":(1,3)},{"name":"Second Controller","seq":(2,3)},{"name":"Priority Contrast","seq":(1,2,3)},{"name":"Blocking Command","seq":(4,2,1,3)},{"name":"Exploit Arbitration","seq":(2,3,1,4,2,1,3)},{"name":"Command Arbitration","seq":(1,2,3,4,1,3,2,4,1,3)}]
def advance(s,a):
 pos,phase,priority,history,blockers,exploited=s
 if a in (1,2):
  commands=(a,1+(phase%2),2-(phase%2));winner=commands[priority[0]];pos=(pos+(-1 if winner==1 else 1))%10;history=history+((commands,winner,pos),);phase+=1
 elif a==3:history=history+(((0,phase%3,2),phase%3,pos),)
 elif a==4:blockers=blockers+((phase%3,pos),);priority=priority[1:]+priority[:1];phase+=1
 elif a==5:exploited=(pos,phase,priority,history[-5:],blockers[-3:])
 return pos,phase,priority,history,blockers,exploited
for x in LEVELS:
 s=(4,0,(1,0,2),(),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=PLATFORM;f[24:34,7:57]=RAIL;x=8+g.pos*5;f[25:33,x:x+5]=RESOLVED
  for i,c in enumerate((PLAYER,AUTO,AUTO)):f[8:17,9+i*17:22+i*17]=c
  for i,_ in enumerate(g.history[-4:]):f[40:46,8+i*12:17+i*12]=RESOLVED
  for i,_ in enumerate(g.blockers[-3:]):f[50:55,8+i*14:18+i*14]=BLOCKER
  if g.exploited:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A032(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a032",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.pos=4;self.phase=0;self.priority=(1,0,2);self.history=self.blockers=();self.exploited=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.pos,self.phase,self.priority,self.history,self.blockers,self.exploited=advance((self.pos,self.phase,self.priority,self.history,self.blockers,self.exploited),a)
  elif a==6:
   if (self.pos,self.phase,self.priority,self.history,self.blockers,self.exploited)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
