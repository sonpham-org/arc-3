"""a033 Twin Stacks -- route buried pieces using only LIFO top access."""
from copy import deepcopy
from arcengine import ARCBaseGame,Camera,Level,RenderableUserDisplay
BG,VAULT,WELL,PIECE,TOP,OUTPUT,TARGET,GOAL,BAD=2,10,8,14,11,6,12,13,15
LEVELS=[{"name":"First Push","seq":(1,)},{"name":"Other Well","seq":(2,1)},{"name":"Pop Output","seq":(3,1,2)},{"name":"Swap Wells","seq":(4,2,1,3)},{"name":"Buried Order","seq":(2,3,1,4,2,1)},{"name":"Twin Stacks","seq":(1,2,3,4,1,3,2,4,1)}]
def advance(s,a):
 stacks,active,output,source,history,program=s;st=[list(x) for x in stacks];src=list(source);out=list(output)
 if a==1:
  if src:st[active].append(src.pop(0))
 elif a==2:active^=1
 elif a==3:
  if st[active]:out.append(st[active].pop())
  history=history+((tuple(map(tuple,st)),active,tuple(out)),)
 elif a==4:
  if st[active]:st[active^1].append(st[active].pop())
  active^=1
 elif a==5:program=(tuple(map(tuple,st)),active,tuple(out),tuple(src),history[-4:])
 return tuple(map(tuple,st)),active,tuple(out),tuple(src),history,program
for x in LEVELS:
 s=(((),()),0,(),(1,2,3,4,5),(),None)
 for a in x["seq"]:s=advance(s,a)
 x["plan"]=x["seq"]+(5,);x["target"]=advance(s,5)
class D(RenderableUserDisplay):
 def __init__(self,g):self.g=g
 def render_interface(self,f):
  g=self.g;f[:,:]=BG;f[4:60,4:60]=VAULT
  f[1:4,8:28]=PIECE;f[1:4,32:52]=TOP
  for side,stack in enumerate(g.stacks):x=9+side*28;f[8:42,x:x+20]=WELL
  for side,stack in enumerate(g.stacks):
   x=11+side*28
   for i,v in enumerate(stack[-5:]):f[35-i*6:40-i*6,x:x+16]=TOP if i==len(stack[-5:])-1 else PIECE
  for i,v in enumerate(g.output[-5:]):f[47:53,8+i*9:15+i*9]=OUTPUT
  f[55:59,8:8+len(g.source)*8]=TARGET
  if g.program:f[51:58,49:57]=GOAL
  if g.bad:f[0:3,18:46]=BAD
  return f
class A033(ARCBaseGame):
 def __init__(self):
  self.display=D(self);self.bad=False;self._reset();self.cfg=LEVELS[0];self.target=self.cfg["target"];ls=[Level(sprites=[],grid_size=(64,64),data=deepcopy(x),name=x["name"]) for x in LEVELS];super().__init__("a033",ls,Camera(0,0,64,64,BG,BG,[self.display]),False,6,[1,2,3,4,5,6])
 def _reset(self):self.stacks=((),());self.active=0;self.output=();self.source=(1,2,3,4,5);self.history=();self.program=None
 def on_set_level(self,l):self.cfg=LEVELS[self.level_index];self._reset();self.bad=False;self.target=self.cfg["target"]
 def step(self):
  a=self.action.id.value
  if a==0:self.complete_action();return
  if a in (1,2,3,4,5):self.stacks,self.active,self.output,self.source,self.history,self.program=advance((self.stacks,self.active,self.output,self.source,self.history,self.program),a)
  elif a==6:
   if (self.stacks,self.active,self.output,self.source,self.history,self.program)==self.target:self.next_level()
   else:self.bad=True;self.lose()
  self.complete_action()
