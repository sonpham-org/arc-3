"""a128 Majority Relation -- move a divider before a simultaneous majority update."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay

BG,FIELD,STATE_A,STATE_B,DIVIDER,CURSOR,NEXT_A,NEXT_B,MATCH,MISS=10,8,12,14,9,13,4,11,6,7
BAD=15
TARGET=(1,1,0,1,0,0,1,0)
LEVELS=[
 {"name":"Move Divider","seq":(1,)},{"name":"Select Object","seq":(2,)},
 {"name":"Flip State","seq":(3,1)},{"name":"Update Majority","seq":(1,2,3,4,2)},
 {"name":"Change Population","seq":(1,3,2,1,4,3,2)},{"name":"Majority Relation","seq":(1,2,3,1,4,2,3,1,4,3)},
]
def advance(s,a):
 states,divider,cursor,next_states,matches,history,snapshot=s;st=list(states)
 if a==1:divider=1+(divider%7);history=(history+(1,))[-8:]
 elif a==2:cursor=(cursor+1)%8;history=(history+(2,))[-8:]
 elif a==3:st[cursor]=1-st[cursor];history=(history+(3,))[-8:]
 elif a==4:
  left=st[:divider];right=st[divider:];lm=int(sum(left)*2>=len(left));rm=int(sum(right)*2>=len(right));next_states=tuple(lm if i<divider else rm for i in range(8));matches=sum(int(x==y) for x,y in zip(next_states,TARGET));history=(history+(4,))[-8:]
 elif a==5:snapshot=(tuple(st),divider,cursor,next_states,matches,history)
 return tuple(st),divider,cursor,next_states,matches,history,snapshot
for q in LEVELS:
 s=((0,1,1,0,1,0,0,1),4,0,(),0,(),None)
 for a in q["seq"]:s=advance(s,a)
 q["plan"]=q["seq"]+(5,);q["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=FIELD
  for i,state in enumerate(g.states):
   x=7+i*7;f[18:30,x:x+6]=STATE_A if state==0 else STATE_B
   if i==g.cursor:f[14:17,x:x+6]=CURSOR
  dx=7+g.divider*7;f[10:48,dx:dx+2]=DIVIDER
  for i,state in enumerate(g.next_states):x=7+i*7;f[35:45,x:x+6]=NEXT_A if state==0 else NEXT_B
  f[54:58,8:8+g.matches*6]=MATCH;f[7:10,8:8+(8-g.matches)*5]=MISS
  if g.bad:f[1:4,18:46]=BAD
  return f
class A128(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(q),name=q["name"]) for q in LEVELS];super().__init__("a128",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.states,self.divider,self.cursor,self.next_states,self.matches,self.history,self.snapshot=((0,1,1,0,1,0,0,1),4,0,(),0,(),None)
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.states,self.divider,self.cursor,self.next_states,self.matches,self.history,self.snapshot=advance((self.states,self.divider,self.cursor,self.next_states,self.matches,self.history,self.snapshot),a)
  elif a==6:
   if (self.states,self.divider,self.cursor,self.next_states,self.matches,self.history,self.snapshot)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
